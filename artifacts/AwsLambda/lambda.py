import boto3
import pandas as pd
import re

from io import StringIO
from datetime import datetime, timezone


# ============================================================
# AWS
# ============================================================

s3 = boto3.client("s3")


# ============================================================
# CONFIGURATION
# ============================================================

BUCKET = "rawdatafp"

STAGING_PREFIX = "staging/individual"
OUTPUT_KEY = "csv_transactions_consolidated/consolidated_transactions.csv"
AUDIT_PREFIX = "duplicate_audit/2026/08/"

# New: customer identity registry (source of truth for resolved customers)
CUSTOMER_REGISTRY_KEY = "customer_registry/customers.csv"
MERGE_AUDIT_PREFIX = "identity_merge_audit/2026/08/"

DUPLICATE_THRESHOLD_SECONDS = 2
AGE_TOLERANCE = 2  # years, for phone+name+age matching

IDENTITY_COLUMNS = [
    "Customer ID", "Age", "Gender", "Location", "Online/Offline",
    "Category", "Item Purchased", "Brand", "Color", "Size", "Quantity",
    "Purchase Amount (₹)", "Discount (%)", "Festival/Sale",
    "Subscription Status", "Payment Method", "Online Store",
    "Shipping Charge (₹)", "Delivery Speed", "Delivery Time (Days)",
]
EXPECTED_COLUMNS = [
    "Transaction ID",
    "Customer ID",
    "Customer Full Name",
    "Customer Email",
    "Customer Phone",
    "Purchase Date",
    "Age",
    "Gender",
    "Location",
    "Online/Offline",
    "Category",
    "Item Purchased",
    "Brand",
    "Previous Purchases",
    "Color",
    "Size",
    "Quantity",
    "Purchase Amount (₹)",
    "Discount (%)",
    "Festival/Sale",
    "Subscription Status",
    "Payment Method",
    "Review Rating",
    "Return Status",
    "Online Store",
    "Shipping Charge (₹)",
    "Delivery Speed",
    "Delivery Time (Days)",
]

CUSTOMER_REGISTRY_COLUMNS = [
    "Customer ID",
    "Customer Full Name",
    "Customer Email",
    "Customer Phone",
    "normalized_phone",
    "Age",
]


# ============================================================
# HELPERS
# ============================================================

def read_csv_from_s3(bucket, key):
    response = s3.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read().decode("utf-8")
    return pd.read_csv(StringIO(content))


def normalize_phone(value):
    if pd.isna(value):
        return None
    return re.sub(r"[^0-9]", "", str(value))


def write_csv_to_s3(df, bucket, key):
    buffer = StringIO()
    df.to_csv(buffer, index=False)
    s3.put_object(Bucket=bucket, Key=key, Body=buffer.getvalue())


# ============================================================
# CUSTOMER REGISTRY
# ============================================================

def read_customer_registry():
    """
    Loads the persistent customer identity table.
    Falls back to an empty registry if it doesn't exist yet
    (first run).
    """
    try:
        registry = read_csv_from_s3(BUCKET, CUSTOMER_REGISTRY_KEY)
    except s3.exceptions.NoSuchKey:
        registry = pd.DataFrame(columns=CUSTOMER_REGISTRY_COLUMNS)

    if "normalized_phone" not in registry.columns:
        registry["normalized_phone"] = registry.get(
            "Customer Phone", pd.Series(dtype=str)
        ).apply(normalize_phone)

    return registry


def next_customer_id(registry):
    """
    Scans the registry for the highest CUST###### and returns the next one.
    NOTE: safe only for a single Lambda invocation processing all files
    sequentially in one pass, as done here. If this Lambda can ever run
    concurrently, this counter needs to move to something atomic
    (e.g. a DynamoDB counter) instead of being derived from the CSV.
    """
    if registry.empty:
        return 1000

    numeric_ids = (
        registry["Customer ID"]
        .str.extract(r"CUST(\d+)")[0]
        .dropna()
        .astype(int)
    )

    return (numeric_ids.max() + 1) if not numeric_ids.empty else 1000


# ============================================================
# IDENTITY RESOLUTION (VALIDATION STEP)
# ============================================================

def resolve_pending_customers(df, registry):
    """
    For every row with a PENDING-<uuid> Customer ID:
      Tier 1 - exact email match against the registry      -> reuse ID
      Tier 2 - phone + full name + age match (age tolerance) -> reuse ID
      No match                                             -> assign new ID

    Returns:
      df       - with Customer ID values resolved in place
      registry - updated with any newly created customers
      audit_records - list of dicts describing each resolution decision
    """

    df = df.copy()
    df["normalized_phone"] = df.get(
        "Customer Phone", pd.Series(dtype=str, index=df.index)
    ).apply(normalize_phone)

    next_id_counter = next_customer_id(registry)
    audit_records = []

    pending_mask = df["Customer ID"].str.startswith("PENDING-", na=False)

    for index in df[pending_mask].index:

        row = df.loc[index]
        matched_id = None
        match_signals = None

        # ------------------------------------------------
        # Tier 1: email match
        # ------------------------------------------------
        email_matches = registry[
            registry["Customer Email"] == row["Customer Email"]
        ]

        if not email_matches.empty:
            matched_id = email_matches.iloc[0]["Customer ID"]
            match_signals = "email"

        # ------------------------------------------------
        # Tier 2: phone + full name + age
        # ------------------------------------------------
        if matched_id is None and row["normalized_phone"]:

            candidates = registry[
                (registry["normalized_phone"] == row["normalized_phone"])
                & (registry["Customer Full Name"] == row["Customer Full Name"])
                & (
                    (registry["Age"] - row["Age"]).abs()
                    <= AGE_TOLERANCE
                )
            ]

            if not candidates.empty:
                matched_id = candidates.iloc[0]["Customer ID"]
                match_signals = "phone+name+age"

        # ------------------------------------------------
        # Resolve or create
        # ------------------------------------------------
        if matched_id is not None:

            df.loc[index, "Customer ID"] = matched_id

            audit_records.append({
                "pending_transaction_id": row["Transaction ID"],
                "resolved_customer_id": matched_id,
                "resolution": "merged_existing",
                "match_signals": match_signals,
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            })

        else:

            new_id = f"CUST{next_id_counter:06d}"
            next_id_counter += 1

            df.loc[index, "Customer ID"] = new_id

            new_customer = {
                "Customer ID": new_id,
                "Customer Full Name": row["Customer Full Name"],
                "Customer Email": row["Customer Email"],
                "normalized_phone": row["normalized_phone"],
                "Age": row["Age"],
            }

            registry = pd.concat(
                [registry, pd.DataFrame([new_customer])],
                ignore_index=True,
            )

            audit_records.append({
                "pending_transaction_id": row["Transaction ID"],
                "resolved_customer_id": new_id,
                "resolution": "new_customer",
                "match_signals": None,
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            })

    df = df.drop(columns=["normalized_phone"])

    return df, registry, audit_records


def find_duplicates(df):

    # Sort by identity columns and Purchase Date.
    # Therefore, the first transaction in each group
    # is always the oldest.

    df = df.sort_values(
        IDENTITY_COLUMNS + ["Purchase Date"]
    ).reset_index(drop=True)

    duplicate_indices = []
    audit_records = []

    # Process each group of identical identity fields
    for _, group in df.groupby(
        IDENTITY_COLUMNS,
        dropna=False,
        sort=False
    ):
        group = group.sort_values("Purchase Date")

        anchor_index = group.index[0]
        anchor_date = group.loc[anchor_index, "Purchase Date"]
        anchor_transaction_id = group.loc[anchor_index, "Transaction ID"]

        for index in group.index[1:]:
            current_date = group.loc[index, "Purchase Date"]
            difference = (current_date - anchor_date).total_seconds()

            if difference <= DUPLICATE_THRESHOLD_SECONDS:
                duplicate_indices.append(index)
                audit_record = group.loc[index].to_dict()
                audit_record["duplicate_reason"] = (
                    "Same identity fields and Purchase Date difference <= 2 seconds"
                )
                audit_record["kept_transaction_id"] = anchor_transaction_id
                audit_record["kept_purchase_date"] = anchor_date
                audit_record["time_difference_seconds"] = difference
                audit_record["processed_at"] = datetime.now(timezone.utc).isoformat()
                audit_records.append(audit_record)
            else:
                anchor_index = index
                anchor_date = current_date
                anchor_transaction_id = group.loc[index, "Transaction ID"]

    return duplicate_indices, audit_records


# ============================================================
# LAMBDA
# ============================================================

def lambda_handler(event, context):

    print("Starting transaction consolidation.")

    # --------------------------------------------------------
    # 1. Find staging CSV files
    # --------------------------------------------------------

    response = s3.list_objects_v2(Bucket=BUCKET, Prefix=STAGING_PREFIX)
    csv_files = [
        obj["Key"] for obj in response.get("Contents", [])
        if obj["Key"].lower().endswith(".csv")
    ]

    if not csv_files:
        print("No CSV files found.")
        return {"statusCode": 200, "message": "No CSV files found."}

    print(f"CSV files found: {len(csv_files)}")

    # --------------------------------------------------------
    # 2. Read + validate CSV files
    # --------------------------------------------------------

    dataframes = []

    for file_key in csv_files:
        print(f"Reading {file_key}")
        df = read_csv_from_s3(BUCKET, file_key)

        missing_columns = [c for c in EXPECTED_COLUMNS if c not in df.columns]
        if missing_columns:
            raise ValueError(f"{file_key} is missing columns: {missing_columns}")

        df = df[EXPECTED_COLUMNS].copy()
        df["_source_file"] = file_key
        dataframes.append(df)

    # --------------------------------------------------------
    # 3. Concatenate
    # --------------------------------------------------------

    df = pd.concat(dataframes, ignore_index=True)
    rows_before = len(df)
    print(f"Rows before cleaning: {rows_before}")

    # --------------------------------------------------------
    # 4. Convert Purchase Date
    # --------------------------------------------------------

    df["Purchase Date"] = pd.to_datetime(df["Purchase Date"], errors="coerce")

    invalid_dates = df["Purchase Date"].isna().sum()
    if invalid_dates > 0:
        raise ValueError(f"{invalid_dates} transactions have invalid Purchase Date values.")

    # --------------------------------------------------------
    # 5. VALIDATION STEP: resolve pending customer identities
    # --------------------------------------------------------

    registry = read_customer_registry()

    df, registry, merge_audit_records = resolve_pending_customers(
        df, registry
    )

    pending_resolved = len(merge_audit_records)
    print(f"Pending customer rows resolved: {pending_resolved}")

    # Persist the updated registry immediately
    write_csv_to_s3(registry, BUCKET, CUSTOMER_REGISTRY_KEY)

    if merge_audit_records:
        merge_audit_df = pd.DataFrame(merge_audit_records)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        merge_audit_key = f"{MERGE_AUDIT_PREFIX}identity_resolution_{timestamp}.csv"
        write_csv_to_s3(merge_audit_df, BUCKET, merge_audit_key)
        print(f"Identity resolution audit written to s3://{BUCKET}/{merge_audit_key}")

    # --------------------------------------------------------
    # 6. Find + remove duplicates
    # --------------------------------------------------------

    duplicate_indices, audit_records = find_duplicates(df)
    print(f"Duplicates found: {len(duplicate_indices)}")

    cleaned_df = df.drop(index=duplicate_indices).copy()
    rows_after = len(cleaned_df)
    print(f"Rows after cleaning: {rows_after}")

    # --------------------------------------------------------
    # 7. Remove internal column + write consolidated CSV
    # --------------------------------------------------------

    cleaned_df = cleaned_df[EXPECTED_COLUMNS]
    write_csv_to_s3(cleaned_df, BUCKET, OUTPUT_KEY)
    print(f"Consolidated file written to s3://{BUCKET}/{OUTPUT_KEY}")

    # --------------------------------------------------------
    # 8. Delete staging files
    # --------------------------------------------------------

    for file_key in csv_files:
        s3.delete_object(Bucket=BUCKET, Key=file_key)
        print(f"Deleted staging file: {file_key}")

    # --------------------------------------------------------
    # 9. Write duplicate audit log
    # --------------------------------------------------------

    audit_key = None

    if audit_records:
        audit_df = pd.DataFrame(audit_records)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        audit_key = f"{AUDIT_PREFIX}duplicate_log_{timestamp}.csv"
        write_csv_to_s3(audit_df, BUCKET, audit_key)
        print(f"Audit log written to s3://{BUCKET}/{audit_key}")

    # --------------------------------------------------------
    # 10. Return result
    # --------------------------------------------------------

    return {
        "statusCode": 200,
        "files_processed": len(csv_files),
        "rows_before": rows_before,
        "duplicates_removed": len(duplicate_indices),
        "rows_after": rows_after,
        "pending_customers_resolved": pending_resolved,
        "consolidated_file": f"s3://{BUCKET}/{OUTPUT_KEY}",
        "duplicate_audit": f"s3://{BUCKET}/{audit_key}" if audit_key else None,
    }


if __name__ == "__main__":
    result = lambda_handler({}, None)
    print(result)