document.getElementById("files").addEventListener("change", function (event) {
  const selectedFilesContainer = document.getElementById("selectedFiles");
  selectedFilesContainer.innerHTML = "";
  const files = event.target.files;
  for (const file of files) {
    const li = document.createElement("li");
    li.textContent = file.name;
    selectedFilesContainer.appendChild(li);
  }
});

document
  .getElementById("uploadForm")
  .addEventListener("submit", async function (event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const errorData = await response.json();
        alert("Error: " + errorData.detail);
        return;
      }
      const data = await response.json();
      const fileList = document.getElementById("fileList");
      const noFilesMsg = document.getElementById("noFiles");
      if (noFilesMsg) {
        noFilesMsg.remove();
      }
      data.files.forEach((file) => {
        const li = document.createElement("li");
        li.id = "file-" + file.id;
        li.innerHTML = `<div class="flex flex-center flex-space-between"><a href="${file.download_url}" target="_blank">${file.file_name}</a>
                          <button class="delete-btn btn" data-file-id="${file.id}">Löschen</button></div> `;
        fileList.appendChild(li);
      });
      form.reset();
      document.getElementById("selectedFiles").innerHTML = "";
    } catch (error) {
      console.error("Upload failed", error);
      alert("Upload failed");
    }
  });

document
  .getElementById("fileList")
  .addEventListener("click", async function (event) {
    if (event.target?.matches(".delete-btn")) {
      const fileId = event.target.getAttribute("data-file-id");
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
          const errorData = await response.json();
          alert("Error: " + errorData.detail);
          return;
        }
        const li = document.getElementById("file-" + fileId);
        if (li) {
          li.remove();
        }
        if (!document.getElementById("fileList").children.length) {
          const p = document.createElement("p");
          p.id = "noFiles";
          p.textContent = "Keine Datei wurde Hochgeladen.";
          document.getElementById("fileList").appendChild(p);
        }
      } catch (error) {
        console.error("Delete failed", error);
        alert("Delete failed");
      }
    }
  });

document.getElementById("finalizeBtn").addEventListener("click", function () {
  const personId = document.querySelector(
    'input[name="person_identifier"]'
  ).value;
  window.location.href = `/create_db_records?person_identifier=${personId}`;
});
