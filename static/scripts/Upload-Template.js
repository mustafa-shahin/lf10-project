function getFileIcon(filenameOrType) {
  const validImageRegex = /\.(jpg|jpeg|png|webp)$/i;
  if (validImageRegex.test(filenameOrType)) {
    return "/static/icons/photo.png";
  }
  return "/static/icons/pdf.png";
}
/**
 * @param {Object} fileData - Contains file info (name, download_url, id, etc.)
 * @returns {HTMLLIElement} The constructed list item element.
 */
function createFileListItem(fileData) {
  const filename = fileData.file_name || fileData.name || "unnamed_file";
  const downloadUrl = fileData.download_url || "#";

  const fileLink = document.createElement("a");
  fileLink.classList.add("flex", "flex-center", "no-link-style");
  fileLink.href = downloadUrl;

  fileLink.innerHTML = `
    <img 
      src="${getFileIcon(filename)}" 
      alt="File Icon" 
      style="width:24px; height:24px; margin-right:8px;"
    >
    ${filename}
  `;

  const fileContainer = document.createElement("div");
  fileContainer.classList.add("flex", "flex-center", "flex-space-between");
  fileContainer.appendChild(fileLink);

  if (fileData.id) {
    const deleteButton = document.createElement("button");
    deleteButton.classList.add("delete-btn", "btn", "margin-0");
    deleteButton.textContent = "Löschen";
    deleteButton.setAttribute("data-file-id", fileData.id);
    fileContainer.appendChild(deleteButton);
  }

  const li = document.createElement("li");
  if (fileData.id) {
    li.id = `file-${fileData.id}`;
  }
  li.classList.add("no-list-style");
  li.appendChild(fileContainer);

  return li;
}

/**
 * Displays  selected files
 */
document.getElementById("files").addEventListener("change", (event) => {
  const selectedFilesContainer = document.getElementById("selectedFiles");
  selectedFilesContainer.innerHTML = ""; // Clear any previous selection
  const files = event.target.files;

  if (!files?.length) return;

  for (const file of files) {
    const li = createFileListItem(file);
    selectedFilesContainer.appendChild(li);
    selectedFilesContainer.classList.remove("hidden");
  }
});

/**
 * upload files to the db and update the file list.
 */
document
  .getElementById("uploadForm")
  .addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        // Attempt to parse JSON error if present
        let errorMsg = "Unknown error occurred.";
        try {
          const errorData = await response.json();
          errorMsg = errorData.detail || errorMsg;
        } catch (err) {
          /* fallback if parsing fails */
        }
        alert("Error: " + errorMsg);
        return;
      }

      const data = await response.json();
      const fileList = document.getElementById("fileList");
      const noFilesMsg = document.getElementById("noFiles");

      // Remove "no files" message if it's there
      if (noFilesMsg) {
        noFilesMsg.remove();
      }

      if (Array.isArray(data.files)) {
        data.files.forEach((file) => {
          const li = createFileListItem(file);
          fileList.appendChild(li);
        });
      }

      // Reset form and the selected files preview
      form.reset();
      document.getElementById("selectedFiles").innerHTML = "";
    } catch (error) {
      console.error("Upload failed:", error);
      alert("Upload failed. Check the console for details.");
    }
  });

document.getElementById("fileList").addEventListener("click", async (event) => {
  if (event.target?.matches(".delete-btn")) {
    const fileId = event.target.getAttribute("data-file-id");
    if (!fileId) return;

    try {
      const personId = document.querySelector(
        'input[name="person_identifier"]'
      ).value;
      const response = await fetch(
        `/file/${fileId}?person_identifier=${personId}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        // Attempt to parse JSON error
        let errorMsg = "Unknown error occurred.";
        try {
          const errorData = await response.json();
          errorMsg = errorData.detail || errorMsg;
        } catch (err) {
          /* fallback if parsing fails */
        }
        alert("Error: " + errorMsg);
        return;
      }

      // If successful, remove the LI from the list
      const li = document.getElementById("file-" + fileId);
      if (li) {
        li.remove();
      }

      // If no more files, show the "no files" message
      const fileList = document.getElementById("fileList");
      if (!fileList.children.length) {
        const p = document.createElement("p");
        p.id = "noFiles";
        p.textContent = "Keine Datei wurde Hochgeladen.";
        fileList.appendChild(p);
      }
    } catch (error) {
      console.error("Delete failed:", error);
      alert("Delete failed. Check the console for details.");
    }
  }
});

/**
 * Handler for the "finalize" button
 */
document.getElementById("finalizeBtn").addEventListener("click", () => {
  const personId = document.querySelector(
    'input[name="person_identifier"]'
  ).value;
  if (!personId) {
    alert("Person identifier is missing.");
    return;
  }
  // Navigate to your finalize endpoint
  window.location.href = `/create_db_records?person_identifier=${personId}`;
});
