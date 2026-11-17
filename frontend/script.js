
const fileInput = document.getElementById("fileInput");
const dropzone = document.getElementById("dropzone");

const profileBtn = document.getElementById("profileBtn");
const cleanBtn = document.getElementById("cleanBtn");
const downloadButton = document.getElementById("downloadButton");

let selectedFile = null;
let downloadUrl = null;


// File selection
fileInput.addEventListener("change", () => {
    handleFile(fileInput.files[0]);
});


// Handle selected file
function handleFile(file) {

    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".csv")) {

        alert("Please select a CSV file.");

        selectedFile = null;
        fileInput.value = "";

        document.getElementById("fileName").textContent =
            "Choose a CSV file";

        document.getElementById("results").hidden = true;
        document.getElementById("cleanedResults").hidden = true;

        document.getElementById("status").textContent = "";
        document.getElementById("cleanStatus").textContent = "";
        document.getElementById("downloadStatus").textContent = "";

        downloadButton.hidden = true;

        if (downloadUrl) {
            URL.revokeObjectURL(downloadUrl);
            downloadUrl = null;
        }

        return;
    }

    selectedFile = file;

    document.getElementById("fileName").textContent = file.name;

    document.getElementById("results").hidden = true;
    document.getElementById("cleanedResults").hidden = true;

    document.getElementById("status").textContent = "";
    document.getElementById("cleanStatus").textContent = "";
    document.getElementById("downloadStatus").textContent = "";

    downloadButton.hidden = true;

    if (downloadUrl) {
        URL.revokeObjectURL(downloadUrl);
        downloadUrl = null;
    }
}


// Drag and drop
dropzone.addEventListener("dragover", (event) => {
    event.preventDefault();
});

dropzone.addEventListener("drop", (event) => {
    event.preventDefault();

    const file = event.dataTransfer.files[0];

    if (file) {
        handleFile(file);
        fileInput.value = "";
    }
});


// Reusable table preview function
function displayTable(columns, records, headId, bodyId) {

    const tableHead = document.getElementById(headId);
    const tableBody = document.getElementById(bodyId);

    tableHead.innerHTML = "";
    tableBody.innerHTML = "";

    const headerRow = document.createElement("tr");

    columns.forEach(column => {

        const th = document.createElement("th");
        th.textContent = column;

        headerRow.appendChild(th);
    });

    tableHead.appendChild(headerRow);

    records.forEach(record => {

        const row = document.createElement("tr");

        columns.forEach(column => {

            const cell = document.createElement("td");
            cell.textContent = record[column] ?? "";

            row.appendChild(cell);
        });

        tableBody.appendChild(row);
    });
}


// Analyze CSV
profileBtn.addEventListener("click", async () => {

    if (!selectedFile) {
        alert("Please select a CSV file first.");
        return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);

    profileBtn.disabled = true;

    document.getElementById("status").textContent =
        "Analyzing your dataset...";

    try {

        const response = await fetch("/profile", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Analysis failed.");
        }

        // Dataset overview
        document.getElementById("filename").textContent =
            "File: " + data.filename;

        document.getElementById("rowCount").textContent = data.rows;
        document.getElementById("columnCount").textContent = data.columns;

        const missingTotal = Object.values(data.missing_values)
            .reduce((total, value) => total + value, 0);

        document.getElementById("missingCount").textContent =
            missingTotal;

        document.getElementById("duplicateCount").textContent =
            data.duplicate_rows;


        // Column information
        const columnTable = document.getElementById("columnTable");

        columnTable.innerHTML = "";

        data.column_names.forEach(column => {

            const row = document.createElement("tr");

            const nameCell = document.createElement("td");
            nameCell.textContent = column;

            const typeCell = document.createElement("td");
            typeCell.textContent = data.data_types[column];

            const missingCell = document.createElement("td");
            missingCell.textContent = data.missing_values[column] ?? 0;

            row.appendChild(nameCell);
            row.appendChild(typeCell);
            row.appendChild(missingCell);

            columnTable.appendChild(row);
        });


        // Original data preview
        displayTable(
            data.column_names,
            data.preview,
            "previewHead",
            "previewBody"
        );

        document.getElementById("results").hidden = false;

        document.getElementById("status").textContent =
            "Analysis completed successfully.";

    } catch (error) {

        document.getElementById("status").textContent =
            "Error: " + error.message;

    } finally {

        profileBtn.disabled = false;
    }
});


// Clean CSV
cleanBtn.addEventListener("click", async () => {

    if (!selectedFile) {
        alert("Please select a CSV file first.");
        return;
    }

    const formData = new FormData();

    formData.append("file", selectedFile);

    formData.append(
        "remove_duplicates",
        document.getElementById("removeDuplicates").checked
    );

    formData.append(
        "missing_strategy",
        document.getElementById("missingStrategy").value
    );

    cleanBtn.disabled = true;

    document.getElementById("cleanStatus").textContent =
        "Cleaning your dataset...";

    document.getElementById("cleanedResults").hidden = true;

    downloadButton.hidden = true;

    if (downloadUrl) {
        URL.revokeObjectURL(downloadUrl);
        downloadUrl = null;
    }

    try {

        const response = await fetch("/clean", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Cleaning failed.");
        }

        if (!data.cleaned_csv) {
            throw new Error("Cleaned CSV data was not received.");
        }


        // Cleaning statistics
        document.getElementById("originalRows").textContent =
            data.original_rows;

        document.getElementById("cleanedRows").textContent =
            data.cleaned_rows;

        document.getElementById("duplicatesRemoved").textContent =
            data.duplicates_removed;

        document.getElementById("missingRemaining").textContent =
            data.missing_values_remaining;


        // Actual cleaned dataset preview
        displayTable(
            data.columns,
            data.preview,
            "cleanedPreviewHead",
            "cleanedPreviewBody"
        );


        // Prepare file but do not download yet
        const blob = new Blob(
            ["\uFEFF", data.cleaned_csv],
            { type: "text/csv;charset=utf-8;" }
        );

        downloadUrl = URL.createObjectURL(blob);

        document.getElementById("cleanStatus").textContent =
            "Dataset cleaned successfully. Review the results below.";

        document.getElementById("cleanedResults").hidden = false;

        downloadButton.hidden = false;

    } catch (error) {

        document.getElementById("cleanStatus").textContent =
            "Error: " + error.message;

    } finally {

        cleanBtn.disabled = false;
    }
});


// Download only after customer clicks
downloadButton.addEventListener("click", () => {

    if (!downloadUrl) {
        alert("Please clean your dataset first.");
        return;
    }

    const link = document.createElement("a");

    link.href = downloadUrl;
    link.download = "cleaned_data.csv";

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    document.getElementById("downloadStatus").textContent =
        "Your cleaned CSV download has been requested.";
});
