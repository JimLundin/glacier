"""
Generate sample data for Glacier examples.

Run this to create test data:
    python examples/generate_sample_data.py
"""

import polars as pl
from pathlib import Path

# Create data directory
data_dir = Path(__file__).parent / "data"
data_dir.mkdir(exist_ok=True)

# Generate sample data
sample_data = pl.DataFrame(
    {
        "id": range(1, 101),
        "category": ["A", "B", "C", "D"] * 25,
        "value": [i * 10 + (i % 7) for i in range(1, 101)],
        "date": pl.date_range(
            start=pl.date(2024, 1, 1), end=pl.date(2024, 4, 9), interval="1d", eager=True
        ),
    }
)

# Add some null values to test filtering
sample_data = sample_data.with_columns(
    [
        pl.when(pl.col("id") % 10 == 0).then(None).otherwise(pl.col("value")).alias("value"),
    ]
)

# Save to parquet
output_file = data_dir / "sample.parquet"
sample_data.write_parquet(output_file)

print(f"Sample data generated: {output_file}")
print(f"Shape: {sample_data.shape}")
print(f"\nFirst few rows:")
print(sample_data.head())
