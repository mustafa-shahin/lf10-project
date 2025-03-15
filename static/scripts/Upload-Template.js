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

  const downloadUrl = fileData.id ? `/download/${fileData.id}` : "#";

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
 * Auto-upload files when they are selected
 */
document.getElementById("files").addEventListener("change", async (event) => {
  const files = event.target.files;
  if (!files?.length) return;

  // Get form data
  const form = document.getElementById("uploadForm");
  const formData = new FormData(form);

  // Clear the selected files display first
  const selectedFilesContainer = document.getElementById("selectedFiles");
  selectedFilesContainer.innerHTML = "";

  // Add a loading indicator to the selected files container
  const loadingIndicator = document.createElement("li");
  loadingIndicator.innerHTML = `
    <div class="uploading-indicator">
      <span>Uploading files...</span>
      <div class="spinner"></div>
    </div>
  `;
  selectedFilesContainer.appendChild(loadingIndicator);
  selectedFilesContainer.classList.remove("hidden");

  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      let errorMsg = "Upload failed";
      try {
        const errorData = await response.json();
        errorMsg = errorData.detail || errorMsg;
      } catch (err) {}

      // Update the loading indicator to show error
      loadingIndicator.innerHTML = `<div class="error-message">Error: ${errorMsg}</div>`;
      console.error("Upload failed:", errorMsg);
      return;
    }

    // Upload successful, process response
    const data = await response.json();
    const fileList = document.getElementById("fileList");
    const noFilesMsg = document.getElementById("noFiles");

    if (noFilesMsg) {
      noFilesMsg.remove();
    }

    loadingIndicator.remove();

    if (Array.isArray(data.files)) {
      data.files.forEach((file) => {
        const li = createFileListItem(file);
        fileList.appendChild(li);
      });
    }

    form.reset();
    selectedFilesContainer.innerHTML = "";
  } catch (error) {
    console.error("Upload failed:", error);

    loadingIndicator.innerHTML = `<div class="error-message">Error: ${error.message}</div>`;
  }
});

/**
 * Handle file deletion
 */
document.getElementById("fileList").addEventListener("click", async (event) => {
  if (event.target?.matches(".delete-btn")) {
    const fileId = event.target.getAttribute("data-file-id");
    if (!fileId) return;

    if (!confirm("Sind Sie sicher, dass Sie diese Datei löschen möchten?")) {
      return;
    }
    const deleteButton = event.target;
    deleteButton.disabled = true;
    deleteButton.textContent = "Lösche...";

    try {
      const response = await fetch(`/file/${fileId}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        let errorMsg = "Unknown error occurred.";
        try {
          const errorData = await response.json();
          errorMsg = errorData.detail || errorMsg;
        } catch (err) {}
        alert("Error: " + errorMsg);

        deleteButton.disabled = false;
        deleteButton.textContent = "Löschen";
        return;
      }

      const li = document.getElementById("file-" + fileId);
      if (li) {
        li.remove();
      }

      const fileList = document.getElementById("fileList");
      if (!fileList.children.length) {
        const p = document.createElement("p");
        p.id = "noFiles";
        p.textContent = "Keine Datei wurde hochgeladen.";
        fileList.appendChild(p);
      }
    } catch (error) {
      console.error("Delete failed:", error);
      alert("Delete failed. Check the console for details.");

      deleteButton.disabled = false;
      deleteButton.textContent = "Löschen";
    }
  }
});
