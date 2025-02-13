document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form');
    const requiredFields = form.querySelectorAll('[required]');
    const submitBtn = document.getElementById('submitBtn');

    function checkFields() {
      for (let field of requiredFields) {
        if (!field.value.trim()) {
          submitBtn.disabled = true;
          return;
        }
      }
      submitBtn.disabled = false;
      submitBtn.classList.add('enabled')
    }

    requiredFields.forEach(field => {
      field.addEventListener('input', checkFields);
    });

    checkFields();
  });