import boto3
import pandas as pd

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

STAGING_PREFIX = (
    "staging/individual/"
    "transactions_clean_2026/08/"
)

OUTPUT_KEY = (
    "csv_transactions_consolidated/"
    "consolidated_transactions.csv"
)

AUDIT_PREFIX = (
    "duplicate_audit/"
    "2026/08/"
)

DUPLICATE_THRESHOLD_SECONDS = 2


# ============================================================
# 21 IDENTITY COLUMNS
# ============================================================

IDENTITY_COLUMNS = [
    "Customer ID",
    "Age",
    "Gender",
    "Location",
    "Online/Offline",
    "Category",
    "Item Purchased",
    "Brand",
    "Color",
    "Size",
    "Quantity",
    "Purchase Amount (₹)",
    "Discount (%)",
    "Festival/Sale",
    "Subscription Status",
    "Payment Method",
    "Online Store",
    "Shipping Charge (₹)",
    "Delivery Speed",
    "Delivery Time (Days)",
]


# ============================================================
# ALL EXPECTED COLUMNS
# ============================================================

EXPECTED_COLUMNS = [
    "Transaction ID",
    "Customer ID",
    "Purchase Date",
    "Age",
    "Gender",
    "Location",
    "Online/Offline",
    "Category",
    "Item Purchased",
    "Brand",
    "Color",
    "Size",
    "Quantity",
    "Purchase Amount (₹)",
    "Discount (%)",
    "Festival/Sale",
    "Subscription Status",
    "Payment Method",
    "Return Status",
    "Previous Purchases",
    "Online Store",
    "Shipping Charge (₹)",
    "Delivery Speed",
    "Delivery Time (Days)",
    "Review Rating",
]


# ============================================================
# READ CSV FROM S3
# ============================================================

def read_csv_from_s3(bucket, key):

    response = s3.get_object(
        Bucket=bucket,
        Key=key
    )

    content = response["Body"].read().decode("utf-8")

    return pd.read_csv(
        StringIO(content)
    )


# ============================================================
# FIND DUPLICATES
# ============================================================

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

        group = group.sort_values(
            "Purchase Date"
        )

        # ----------------------------------------------------
        # Start with the oldest transaction
        # ----------------------------------------------------

        anchor_index = group.index[0]

        anchor_date = group.loc[
            anchor_index,
            "Purchase Date"
        ]

        anchor_transaction_id = group.loc[
            anchor_index,
            "Transaction ID"
        ]

        # ----------------------------------------------------
        # Check every subsequent transaction
        # ----------------------------------------------------

        for index in group.index[1:]:

            current_date = group.loc[
                index,
                "Purchase Date"
            ]

            difference = (
                current_date - anchor_date
            ).total_seconds()

            # ------------------------------------------------
            # Duplicate
            # ------------------------------------------------

            if difference <= DUPLICATE_THRESHOLD_SECONDS:

                duplicate_indices.append(index)

                audit_record = (
                    group.loc[index]
                    .to_dict()
                )

                audit_record[
                    "duplicate_reason"
                ] = (
                    "Same identity fields and "
                    "Purchase Date difference "
                    "<= 2 seconds"
                )

                audit_record[
                    "kept_transaction_id"
                ] = anchor_transaction_id

                audit_record[
                    "kept_purchase_date"
                ] = anchor_date

                audit_record[
                    "time_difference_seconds"
                ] = difference

                audit_record[
                    "processed_at"
                ] = datetime.now(
                    timezone.utc
                ).isoformat()

                audit_records.append(
                    audit_record
                )

            # ------------------------------------------------
            # New transaction
            # ------------------------------------------------

            else:

                # This transaction becomes the new anchor.
                #
                # Example:
                #
                # TX001 = 10:00:00
                # TX002 = 10:00:01
                # TX003 = 10:00:03
                #
                # TX003 is >2 seconds from TX001,
                # so TX003 becomes a new transaction group.

                anchor_index = index

                anchor_date = current_date

                anchor_transaction_id = (
                    group.loc[
                        index,
                        "Transaction ID"
                    ]
                )

    return (
        duplicate_indices,
        audit_records
    )


# ============================================================
# LAMBDA
# ============================================================

def lambda_handler(event, context):

    print("Starting transaction consolidation.")

    # --------------------------------------------------------
    # 1. Find staging CSV files
    # --------------------------------------------------------

    response = s3.list_objects_v2(
        Bucket=BUCKET,
        Prefix=STAGING_PREFIX
    )

    csv_files = [
        obj["Key"]
        for obj in response.get("Contents", [])
        if obj["Key"].lower().endswith(".csv")
    ]

    if not csv_files:

        print("No CSV files found.")

        return {
            "statusCode": 200,
            "message": "No CSV files found."
        }

    print(
        f"CSV files found: {len(csv_files)}"
    )

    # --------------------------------------------------------
    # 2. Read CSV files
    # --------------------------------------------------------

    dataframes = []

    for file_key in csv_files:

        print(
            f"Reading {file_key}"
        )

        df = read_csv_from_s3(
            BUCKET,
            file_key
        )

        # ----------------------------------------------------
        # Validate columns
        # ----------------------------------------------------

        missing_columns = [
            column
            for column in EXPECTED_COLUMNS
            if column not in df.columns
        ]

        if missing_columns:

            raise ValueError(
                f"{file_key} is missing columns: "
                f"{missing_columns}"
            )

        df = df[EXPECTED_COLUMNS]

        # Keep source file for audit purposes

        df["_source_file"] = file_key

        dataframes.append(df)

    # --------------------------------------------------------
    # 3. Concatenate
    # --------------------------------------------------------

    df = pd.concat(
        dataframes,
        ignore_index=True
    )

    rows_before = len(df)

    print(
        f"Rows before cleaning: {rows_before}"
    )

    # --------------------------------------------------------
    # 4. Convert Purchase Date
    # --------------------------------------------------------

    df["Purchase Date"] = pd.to_datetime(
        df["Purchase Date"],
        errors="coerce"
    )

    # --------------------------------------------------------
    # 5. Check invalid dates
    # --------------------------------------------------------

    invalid_dates = df[
        "Purchase Date"
    ].isna().sum()

    if invalid_dates > 0:

        raise ValueError(
            f"{invalid_dates} transactions "
            "have invalid Purchase Date values."
        )

    # --------------------------------------------------------
    # 6. Find duplicates
    # --------------------------------------------------------

    (
        duplicate_indices,
        audit_records
    ) = find_duplicates(df)

    print(
        f"Duplicates found: "
        f"{len(duplicate_indices)}"
    )

    # --------------------------------------------------------
    # 7. Remove duplicates
    # --------------------------------------------------------

    cleaned_df = df.drop(
        index=duplicate_indices
    ).copy()

    rows_after = len(cleaned_df)

    print(
        f"Rows after cleaning: {rows_after}"
    )

    # --------------------------------------------------------
    # 8. Remove internal column
    # --------------------------------------------------------

    cleaned_df = cleaned_df[
        EXPECTED_COLUMNS
    ]

    # --------------------------------------------------------
    # 9. Write consolidated CSV
    # --------------------------------------------------------

    output_buffer = StringIO()

    cleaned_df.to_csv(
        output_buffer,
        index=False
    )

    s3.put_object(
        Bucket=BUCKET,
        Key=OUTPUT_KEY,
        Body=output_buffer.getvalue()
    )

    print(
        f"Consolidated file written to "
        f"s3://{BUCKET}/{OUTPUT_KEY}")

    # --------------------------------------------------------
    # 9.5 Delete staging CSV files
    # --------------------------------------------------------

    for file_key in csv_files:

        s3.delete_object(
            Bucket=BUCKET,
            Key=file_key
        )

        print(
            f"Deleted staging file: {file_key}"
        )


    # --------------------------------------------------------
    # 10. Write duplicate audit log
    # --------------------------------------------------------

    audit_key = None

    if audit_records:

        audit_df = pd.DataFrame(
            audit_records
        )

        timestamp = datetime.now(
            timezone.utc
        ).strftime(
            "%Y%m%d_%H%M%S"
        )

        audit_key = (
            f"{AUDIT_PREFIX}"
            f"duplicate_log_"
            f"{timestamp}.csv"
        )

        audit_buffer = StringIO()

        audit_df.to_csv(
            audit_buffer,
            index=False
        )

        s3.put_object(
            Bucket=BUCKET,
            Key=audit_key,
            Body=audit_buffer.getvalue()
        )

        print(
            f"Audit log written to "
            f"s3://{BUCKET}/{audit_key}"
        )

    # --------------------------------------------------------
    # 11. Return result
    # --------------------------------------------------------


    # lots of code...

        return {
        "statusCode": 200,
        "files_processed": len(csv_files),
        "rows_before": rows_before,
        "duplicates_removed": len(duplicate_indices),
        "rows_after": rows_after,
        "consolidated_file": (
            f"s3://{BUCKET}/{OUTPUT_KEY}"
        ),
        "duplicate_audit": (
            f"s3://{BUCKET}/{audit_key}"
            if audit_key
            else None
        )
    }


if __name__ == "__main__":
    event = {}
    context = None

    result = lambda_handler(event, context)

    print(result)