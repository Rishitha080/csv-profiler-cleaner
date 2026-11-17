from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pandas as pd
import io
import csv

app = FastAPI(title="CSV Data Profiler & Cleaner")

app.mount("/static", StaticFiles(directory="frontend"), name="static")

MAX_FILE_SIZE = 5 * 1024 * 1024

SUPPORTED_ENCODINGS = [
    "utf-8-sig",
    "utf-8",
    "cp1252",
    "latin1"
]


def decode_csv_content(content: bytes):

    # Detect UTF-32 BOM before UTF-16 because their BOMs can overlap.
    if content.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        return content.decode("utf-32"), "utf-32"

    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        return content.decode("utf-16"), "utf-16"

    for encoding in SUPPORTED_ENCODINGS:
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue

    raise HTTPException(
        status_code=400,
        detail="Could not decode this CSV file."
    )


def read_csv_file(file: UploadFile):

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a valid CSV file."
        )

    # Read only up to 5 MB + 1 byte.
    content = file.file.read(MAX_FILE_SIZE + 1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty."
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File size exceeds the 5 MB limit."
        )

    try:
        decoded_content, detected_encoding = decode_csv_content(content)

        sample = decoded_content[:8192]

        try:
            dialect = csv.Sniffer().sniff(
                sample,
                delimiters=",;\t|"
            )
            delimiter = dialect.delimiter

        except csv.Error:
            delimiter = ","

        # Validate the raw CSV structure.
        reader = csv.reader(
            io.StringIO(decoded_content, newline=""),
            delimiter=delimiter,
            strict=True
        )

        header = None

        for row in reader:
            if row:
                header = row
                break

        if not header:
            raise HTTPException(
                status_code=400,
                detail="The CSV file contains no readable header."
            )

        # Check empty column names.
        if any(not str(column).strip() for column in header):
            raise HTTPException(
                status_code=400,
                detail="One or more column names are empty."
            )

        # Check duplicate column names.
        normalized_headers = [
            str(column).strip()
            for column in header
        ]

        if len(set(normalized_headers)) != len(normalized_headers):
            raise HTTPException(
                status_code=400,
                detail="Duplicate column names were found. Please make column names unique."
            )

        # Check whether every row has the correct number of fields.
        expected_columns = len(header)

        for row_number, row in enumerate(reader, start=2):

            if not row:
                continue

            if len(row) != expected_columns:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Invalid CSV structure at row {row_number}: "
                        f"expected {expected_columns} fields but found {len(row)}."
                    )
                )

        df = pd.read_csv(
            io.StringIO(decoded_content),
            sep=delimiter,
            on_bad_lines="error",
            skip_blank_lines=True
        )

        if len(df.columns) == 0:
            raise HTTPException(
                status_code=400,
                detail="No columns found in the CSV file."
            )

        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="The CSV file contains no data rows."
            )

        return df, delimiter, detected_encoding

    except HTTPException:
        raise

    except (pd.errors.EmptyDataError, StopIteration):
        raise HTTPException(
            status_code=400,
            detail="The CSV file contains no readable data."
        )

    except (pd.errors.ParserError, csv.Error, UnicodeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid CSV structure or encoding. Please check the file."
        )

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read CSV: {str(error)}"
        )


def create_preview(df, limit=10):

    preview_df = df.head(limit).fillna("")

    preview_df = preview_df.astype(str)

    return preview_df.to_dict(orient="records")


@app.get("/")
def home():
    return FileResponse("frontend/index.html")


@app.post("/profile")
def profile(file: UploadFile = File(...)):

    df, delimiter, encoding = read_csv_file(file)

    missing_values = {
        str(column): int(value)
        for column, value in df.isna().sum().items()
    }

    data_types = {
        str(column): str(dtype)
        for column, dtype in df.dtypes.items()
    }

    return {
        "filename": file.filename,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "delimiter": "Tab" if delimiter == "\t" else delimiter,
        "encoding": encoding,
        "column_names": [str(column) for column in df.columns],
        "data_types": data_types,
        "missing_values": missing_values,
        "duplicate_rows": int(df.duplicated().sum()),
        "preview": create_preview(df, 5)
    }


@app.post("/clean")
def clean(
    file: UploadFile = File(...),
    remove_duplicates: bool = Form(False),
    missing_strategy: str = Form("none")
):

    df, delimiter, encoding = read_csv_file(file)

    original_rows = len(df)

    original_missing = int(df.isna().sum().sum())

    duplicates_removed = 0

    if missing_strategy not in [
        "none",
        "drop_rows",
        "mean",
        "median",
        "mode"
    ]:
        raise HTTPException(
            status_code=400,
            detail="Invalid missing value strategy."
        )

    # Remove duplicate rows.
    if remove_duplicates:

        before_duplicates = len(df)

        df = df.drop_duplicates()

        duplicates_removed = before_duplicates - len(df)

    # Handle missing values.
    if missing_strategy == "drop_rows":

        df = df.dropna()

    elif missing_strategy == "mean":

        numeric_columns = df.select_dtypes(
            include="number"
        ).columns

        for column in numeric_columns:

            if df[column].notna().any():
                df[column] = df[column].fillna(
                    df[column].mean()
                )

    elif missing_strategy == "median":

        numeric_columns = df.select_dtypes(
            include="number"
        ).columns

        for column in numeric_columns:

            if df[column].notna().any():
                df[column] = df[column].fillna(
                    df[column].median()
                )

    elif missing_strategy == "mode":

        for column in df.columns:

            modes = df[column].mode(dropna=True)

            if not modes.empty:
                df[column] = df[column].fillna(modes.iloc[0])

    cleaned_rows = len(df)

    missing_remaining = int(df.isna().sum().sum())

    # Generate cleaned CSV content.
    csv_buffer = io.StringIO()

    df.to_csv(
        csv_buffer,
        index=False,
        sep=delimiter
    )

    cleaned_csv = csv_buffer.getvalue()

    return {
        "success": True,
        "original_rows": int(original_rows),
        "cleaned_rows": int(cleaned_rows),
        "duplicates_removed": int(duplicates_removed),
        "missing_values_before": int(original_missing),
        "missing_values_remaining": int(missing_remaining),
        "columns": [str(column) for column in df.columns],
        "preview": create_preview(df, 10),
        "cleaned_csv": cleaned_csv
    }