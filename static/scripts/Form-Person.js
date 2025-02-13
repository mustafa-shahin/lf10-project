document.addEventListener("DOMContentLoaded", function () {
  const form = document.querySelector("form");
  const requiredFields = form.querySelectorAll("[required]");
  const submitBtn = document.getElementById("submitBtn");

  function checkFields() {
    for (let field of requiredFields) {
      if (
        field.offsetParent !== null && // Ensures it's visible
        ((field.tagName === "INPUT" && !field.value.trim()) ||
          (field.tagName === "SELECT" && field.value === ""))
      ) {
        submitBtn.disabled = true;
        submitBtn.classList.remove("enabled");
        return;
      }
    }
    submitBtn.disabled = false;
    submitBtn.classList.add("enabled");
  }

  requiredFields.forEach((field) => {
    field.addEventListener("input", checkFields);
    field.addEventListener("change", checkFields);
  });

  checkFields();
});
