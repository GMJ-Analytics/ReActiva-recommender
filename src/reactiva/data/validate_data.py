"""
data_validation.py

Validation, null-control, and imputation pipeline for the purchase dataset
used in the recommendation model.

Usage:
    from data_validation import DataValidator, FULL_DEFAULT_STRATEGY

    validator = DataValidator(df)
    validator.print_report()

    # covers every column in the dataset, not just a few
    df_clean = validator.clean(strategy=FULL_DEFAULT_STRATEGY)
"""

from pathlib import Path

import numpy as np
import pandas as pd

from reactiva.data.audit_data import auditar_consistencia_canal
from reactiva.data.save_results import save_to_local


REQUIRED_COLUMNS = ['Customer ID', 'Item Purchased', 'Category', 'Purchase Date']

NUMERIC_VALID_RANGES = {
    'Age': (15, 100),
    'Quantity': (1, None),
    'Purchase Amount (₹)': (0, None),
    'Discount (%)': (0, 100),
    'Shipping Charge (₹)': (0, None),
    'Delivery Time (Days)': (0, None),
    'Review Rating': (1, 5),
    'Previous Purchases': (0, None),
}

# Default strategy covering every column in the 27-column schema.
# Identifiers / fields needed for modeling logic -> drop_row (can't recover these).
# Categorical descriptive fields -> mode (safe, low-stakes to impute).
# Numeric fields -> median (robust to outliers vs. mean).
FULL_DEFAULT_STRATEGY = {
    'Transaction ID':          'drop_row',
    'Customer ID':             'drop_row',
    'Customer Full Name':      'skip',
    'Customer Email':          'skip',
    'Purchase Date':           'drop_row',
    'Age':                     'median',
    'Gender':                  'mode',
    'Location':                'mode',
    'Online/Offline':          'mode',
    'Online Store':            'mode',
    'Category':                'mode',
    'Item Purchased':          'drop_row',
    'Brand':                   'mode',
    'Color':                   'mode',
    'Size':                    'mode',
    'Quantity':                'median',
    'Purchase Amount (₹)':     'median',
    'Discount (%)':            'median',
    'Festival/Sale':           'mode',
    'Shipping Charge (₹)':     'median',
    'Delivery Speed':          'mode',
    'Delivery Time (Days)':    'median',
    'Subscription Status':     'mode',
    'Payment Method':          'mode',
    'Review Rating':           'median',
    'Return Status':           'mode',
    'Previous Purchases':      'median',
    'session':                 'drop_row',
}


class DataValidator:
    """
    Runs configurable data-quality checks and controlled imputation on a
    purchases dataframe. Every step is explicit and logged so nothing gets
    silently altered.
    """

    def __init__(self, df: pd.DataFrame, required_columns=None):
        self.df_raw = df.copy()
        self.df = df.copy()
        self.required_columns = required_columns or REQUIRED_COLUMNS
        self.log = []

    # ------------------------------------------------------------------ #
    # Checks
    # ------------------------------------------------------------------ #
    def run_checks(self) -> dict:
        """Run all validation checks and return a structured report (no mutation)."""
        report = {
            'shape': self.df.shape,
            'missing_columns': self._check_missing_columns(),
            'null_counts': self._check_nulls(),
            'null_pct': self._check_null_pct(),
            'dtypes': self.df.dtypes.astype(str).to_dict(),
            'duplicate_rows': int(self.df.duplicated().sum()),
            'duplicate_key_rows': self._check_duplicate_keys(),
            'date_issues': self._check_dates(),
            'negative_or_zero_ids': self._check_id_sanity(),
            'category_cardinality': self._check_cardinality('Category'),
            'item_cardinality': self._check_cardinality('Item Purchased'),
            'orphan_customers': self._check_orphans(),
            'channel_consistency': self._check_channel_consistency(),
            'range_issues': self._check_numeric_ranges(),
        }
        return report

    def _check_missing_columns(self):
        return [c for c in self.required_columns if c not in self.df.columns]

    def _check_nulls(self):
        return self.df.isnull().sum().to_dict()

    def _check_null_pct(self):
        n = len(self.df)
        if n == 0:
            return {}
        return (self.df.isnull().sum() / n * 100).round(2).to_dict()

    def _check_duplicate_keys(self):
        """Duplicate transactions using Transaction ID, customer, item and date."""
        if 'Transaction ID' not in self.df.columns:
            return None

        keys = [
            c for c in
            ['Transaction ID', 'Customer ID', 'Item Purchased', 'Purchase Date']
            if c in self.df.columns
        ]

        if len(keys) < 2:
            return None

        return int(self.df.duplicated(subset=keys).sum())

    def _check_dates(self):
        if 'Purchase Date' not in self.df.columns:
            return None
        col = self.df['Purchase Date']
        issues = {}
        is_datetime = pd.api.types.is_datetime64_any_dtype(col)
        if not is_datetime:
            issues['not_datetime_dtype'] = True
            parsed = pd.to_datetime(col, errors='coerce')
            issues['unparseable_count'] = int(parsed.isnull().sum() - col.isnull().sum())
            ref = parsed
        else:
            issues['not_datetime_dtype'] = False
            issues['unparseable_count'] = 0
            ref = col
        issues['future_dates'] = int((ref > pd.Timestamp.now()).sum())
        return issues

    def _check_id_sanity(self):
        if 'Customer ID' not in self.df.columns:
            return None
        col = self.df['Customer ID']
        if pd.api.types.is_numeric_dtype(col):
            return int((col <= 0).sum())
        return int((col.astype(str).str.strip() == '').sum())

    def _check_cardinality(self, col):
        if col not in self.df.columns:
            return None
        return int(self.df[col].nunique(dropna=True))

    def _check_orphans(self):
        """Customers with only one purchase ever — flagged, not removed."""
        if 'Customer ID' not in self.df.columns:
            return None
        counts = self.df['Customer ID'].value_counts()
        return int((counts == 1).sum())

    def _check_channel_consistency(self):
        """Reuse channel-consistency rules defined in the data audit."""
        required = [
            'Online/Offline',
            'Online Store',
            'Delivery Speed',
            'Shipping Charge (₹)',
            'Delivery Time (Days)',
        ]

        if any(col not in self.df.columns for col in required):
            return None

        return auditar_consistencia_canal(self.df)

    def _check_numeric_ranges(self):
        """
        Detect values outside defined validity ranges without modifying data.

        Statistical outliers are not treated as invalid values here.
        """
        issues = {}

        for col, (minimum, maximum) in NUMERIC_VALID_RANGES.items():
            if col not in self.df.columns:
                continue

            values = pd.to_numeric(self.df[col], errors='coerce')

            below_min = (
                int((values < minimum).sum())
                if minimum is not None
                else 0
            )

            above_max = (
                int((values > maximum).sum())
                if maximum is not None
                else 0
            )

            issues[col] = {
                'below_min': below_min,
                'above_max': above_max,
            }

        return issues

    def print_report(self, report: dict = None):
        report = report or self.run_checks()
        print('=' * 60)
        print('DATA VALIDATION REPORT')
        print('=' * 60)
        print(f"Shape: {report['shape']}")
        if report['missing_columns']:
            print(f"!! MISSING REQUIRED COLUMNS: {report['missing_columns']}")
        print('\n-- Nulls (count / %) --')
        for col in self.df.columns:
            cnt = report['null_counts'].get(col, 0)
            pct = report['null_pct'].get(col, 0)
            if cnt > 0:
                print(f'  {col}: {cnt} ({pct}%)')
        if all(report['null_counts'].get(c, 0) == 0 for c in self.df.columns):
            print('  none')
        print(f"\nDuplicate rows (all columns identical): {report['duplicate_rows']}")
        print(
            f"Duplicate (Transaction ID, Customer ID, Item, Date) rows: "
            f"{report['duplicate_key_rows']}"
        )
        print(f"\nDate issues: {report['date_issues']}")
        print(f"Customer ID sanity (invalid/empty count): {report['negative_or_zero_ids']}")
        print(f"\nCategory cardinality: {report['category_cardinality']}")
        print(f"Item cardinality: {report['item_cardinality']}")
        print(f"\nCustomers with exactly 1 purchase (orphans): {report['orphan_customers']}")
        print('=' * 60)

    # ------------------------------------------------------------------ #
    # Cleaning / imputation
    # ------------------------------------------------------------------ #
    def clean(
        self,
        strategy: dict,
        dedupe_exact=True,
        dedupe_keys=True,
        parse_dates=True,
        normalize_text=True,
        high_null_threshold=15.0,
        force_impute_above_threshold=False,
    ):
        """
        strategy: dict mapping column -> one of:
            'drop_row'    : drop rows where this column is null
            'mode'        : impute with most frequent value
            'mean'        : impute with column mean (numeric only)
            'median'      : impute with column median (numeric only)
            'ffill'       : forward-fill (useful for time-ordered data per customer)
            'constant:X'  : impute with a fixed value X, e.g. 'constant:Unknown'
            'skip'        : leave nulls as-is (explicit opt-out)

        normalize_text: if True, removes surrounding whitespace from string
            values without changing capitalization or internal content.
            Default True.

        high_null_threshold: max null % (0-100) a column may have before an
            imputation strategy (mode/mean/median/ffill/constant) is BLOCKED
            for that column. 'drop_row' and 'skip' are never blocked, since
            they don't fabricate values. Default 15%.

        force_impute_above_threshold: if True, imputes anyway on columns over
            the threshold (loud warning still printed). If False (default),
            those columns are left untouched (nulls remain) and flagged in
            the log so the decision has to be made explicitly.

        Every action taken is appended to self.log for auditability.
        """
        df = self.df_raw.copy()
        self.log = []
        n_rows = len(df)

        if normalize_text:
            normalized_values = 0

            for col in df.columns:
                if (
                    pd.api.types.is_object_dtype(df[col])
                    or pd.api.types.is_string_dtype(df[col])
                ):
                    string_mask = df[col].map(lambda value: isinstance(value, str))

                    if not string_mask.any():
                        continue

                    before = df.loc[string_mask, col]
                    after = before.str.strip()
                    changed = int((before != after).sum())

                    if changed > 0:
                        df.loc[string_mask, col] = after
                        normalized_values += changed

            self._record(
                f"Normalized surrounding whitespace in text columns. "
                f"{normalized_values} value(s) changed."
            )

        if parse_dates and 'Purchase Date' in df.columns:
            before_na = df['Purchase Date'].isnull().sum()
            df['Purchase Date'] = pd.to_datetime(df['Purchase Date'], errors='coerce')
            after_na = df['Purchase Date'].isnull().sum()
            newly_unparseable = after_na - before_na
            self._record(
                f"Parsed 'Purchase Date' to datetime. "
                f"{newly_unparseable} additional value(s) became NaT (unparseable)."
            )

        for col, action in strategy.items():
            if col not in df.columns:
                self._record(f"Column '{col}' not found — skipped.")
                continue

            null_before = df[col].isnull().sum()
            if null_before == 0:
                self._record(f"'{col}': no nulls, no action needed.")
                continue

            null_pct = (null_before / n_rows * 100) if n_rows else 0
            is_imputation_action = action in ('mode', 'mean', 'median', 'ffill') or \
                (isinstance(action, str) and action.startswith('constant:'))

            if (
                is_imputation_action
                and null_pct > high_null_threshold
                and not force_impute_above_threshold
            ):
                self._record(
                    f"'{col}': {null_before} null(s) ({null_pct:.1f}%) EXCEEDS "
                    f"{high_null_threshold}% threshold — imputation strategy '{action}' BLOCKED. "
                    f"Nulls left as-is. Consider 'drop_row', dropping the column, or passing "
                    f"force_impute_above_threshold=True to override."
                )
                continue

            if (
                is_imputation_action
                and null_pct > high_null_threshold
                and force_impute_above_threshold
            ):
                self._record(
                    f"'{col}': {null_before} null(s) ({null_pct:.1f}%) exceeds "
                    f"{high_null_threshold}% threshold — imputing anyway (forced override)."
                )

            if action == 'drop_row':
                df = df[df[col].notnull()]
                self._record(f"'{col}': dropped {null_before} row(s) with null values.")

            elif action == 'mode':
                if df[col].dropna().empty:
                    self._record(f"'{col}': cannot impute mode, column is entirely null.")
                    continue
                fill_value = df[col].mode().iloc[0]
                df[col] = df[col].fillna(fill_value)
                self._record(
                    f"'{col}': imputed {null_before} null(s) with mode ('{fill_value}')."
                )

            elif action == 'mean':
                if not pd.api.types.is_numeric_dtype(df[col]):
                    self._record(
                        f"'{col}': 'mean' requested on non-numeric column — skipped."
                    )
                    continue
                fill_value = df[col].mean()
                df[col] = df[col].fillna(fill_value)
                self._record(
                    f"'{col}': imputed {null_before} null(s) with mean ({fill_value:.2f})."
                )

            elif action == 'median':
                if not pd.api.types.is_numeric_dtype(df[col]):
                    self._record(
                        f"'{col}': 'median' requested on non-numeric column — skipped."
                    )
                    continue
                fill_value = df[col].median()
                df[col] = df[col].fillna(fill_value)
                self._record(
                    f"'{col}': imputed {null_before} null(s) with median ({fill_value:.2f})."
                )

            elif action == 'ffill':
                sort_cols = [
                    c for c in ['Customer ID', 'Purchase Date']
                    if c in df.columns
                ]
                if sort_cols:
                    df = df.sort_values(sort_cols)
                df[col] = df[col].ffill()
                remaining = df[col].isnull().sum()
                self._record(
                    f"'{col}': forward-filled {null_before - remaining} null(s); "
                    f"{remaining} remain null (leading nulls with no prior value)."
                )

            elif isinstance(action, str) and action.startswith('constant:'):
                fill_value = action.split(':', 1)[1]
                df[col] = df[col].fillna(fill_value)
                self._record(
                    f"'{col}': imputed {null_before} null(s) with constant '{fill_value}'."
                )

            elif action == 'skip':
                self._record(
                    f"'{col}': {null_before} null(s) left as-is (explicit skip)."
                )

            else:
                self._record(f"'{col}': unknown strategy '{action}' — skipped.")

        if dedupe_exact:
            before = len(df)
            df = df.drop_duplicates()
            self._record(
                f"Dropped {before - len(df)} fully duplicate row(s)."
            )

        if dedupe_keys:
            if 'Transaction ID' not in df.columns:
                self._record(
                    "Duplicate-key removal skipped: 'Transaction ID' column not found."
                )
            else:
                keys = [
                    c for c in
                    ['Transaction ID', 'Customer ID', 'Item Purchased', 'Purchase Date']
                    if c in df.columns
                ]

                if len(keys) >= 2:
                    before = len(df)
                    df = df.drop_duplicates(subset=keys)
                    self._record(
                        f"Dropped {before - len(df)} duplicate "
                        "(Transaction ID, Customer ID, Item, Date) row(s)."
                    )

        self.df = df
        return df

    def _record(self, message):
        self.log.append(message)
        print(message)

    def get_log(self):
        return self.log


def clean_and_save_dataset(
    df: pd.DataFrame,
    output_path,
    strategy=None,
) -> pd.DataFrame:
    """
    Clean a purchases dataframe and save the reproducible result as CSV.

    The cleaning logic is delegated to DataValidator and the persistence
    logic is delegated to save_to_local so both behaviours remain centralized.
    """
    strategy = strategy or FULL_DEFAULT_STRATEGY

    validator = DataValidator(df)
    clean_df = validator.clean(strategy=strategy)

    output_path = Path(output_path)
    save_to_local(
        clean_df,
        output_path,
        is_dataframe=True,
    )

    return clean_df


if __name__ == '__main__':
    # Minimal smoke test with sample data containing intentional issues
    sample = pd.DataFrame({
        'Customer ID': [1, 2, 3, None, 5, 5],
        'Item Purchased': ['Kurta', None, 'Saree', 'Jacket', 'Jacket', 'Jacket'],
        'Category': ['Ethnic', 'Ethnic', None, 'Outerwear', 'Outerwear', 'Outerwear'],
        'Purchase Date': [
            '2025-01-01',
            '2025-02-15',
            'not-a-date',
            '2025-03-01',
            '2025-03-01',
            '2025-03-01',
        ],
    })

    validator = DataValidator(sample)
    validator.print_report()

    print('\n--- Cleaning ---')
    df_clean = validator.clean(strategy={
        'Customer ID': 'drop_row',
        'Item Purchased': 'drop_row',
        'Category': 'mode',
        'Purchase Date': 'drop_row',
    })
    print('\nCleaned shape:', df_clean.shape)
    print(df_clean)

# ---------------------------------------------------------------------- #
# Quick usage example against your dataset (df_tovectorize / df):
# ---------------------------------------------------------------------- #
#
# from data_validation import DataValidator
#
# validator = DataValidator(df_tovectorize)
# report = validator.run_checks()
# validator.print_report(report)
#
# df_clean = validator.clean(
#     strategy={
#         'Customer ID': 'drop_row',       # can't recommend without a customer
#         'Item Purchased': 'drop_row',    # can't recommend without an item
#         'Category': 'mode',              # safe to impute, low-stakes field
#         'Purchase Date': 'drop_row',     # needed for season/holdout logic
#     },
#     dedupe_exact=True,
#     dedupe_keys=True,
# )
#
# print(validator.get_log())