function populateSelect(selectElement, options) {
  selectElement.innerHTML = "";
  options.forEach((opt) => {
    const option = document.createElement("option");
    option.value = opt;
    option.textContent = opt.charAt(0).toUpperCase() + opt.slice(1);
    selectElement.appendChild(option);
  });
}

function onLoanTypeChange() {
  const loanType = document.getElementById("loan_type").value;
  const subTypeSelect = document.getElementById("loan_subtype");
  const repayAmountGroup = document.getElementById("repayAmountGroup");
  const termGroup = document.getElementById("termGroup");

  // Hide repay amount and term groups initially
  repayAmountGroup.style.display = "none";
  termGroup.style.display = "none";
  subTypeSelect.innerHTML = "";

  const SOFORT_SUBTYPES = ["tilgung", "endfaellig", "annuitaet"];
  const BAU_SUBTYPES = ["annuitaet"];

  if (loanType === "Sofortkredit") {
    populateSelect(subTypeSelect, SOFORT_SUBTYPES);
  } else if (loanType === "Baudarlehen") {
    populateSelect(subTypeSelect, BAU_SUBTYPES);
  }

  // Show/hide DSCR/CCR fields based on loan type and toggle their required/disabled status
  const dscrFields = document.querySelectorAll(
    "#available_income, #total_debt_payments, #collateral_value, #total_outstanding_debt"
  );
  dscrFields.forEach((field) => {
    let input = field.querySelector("input");
    if (loanType === "Baudarlehen") {
      field.style.display = "flex";
      if (input) {
        input.required = true;
        input.disabled = false;
      }
    } else {
      field.style.display = "none";
      if (input) {
        input.required = false;
        input.disabled = true;
      }
    }
  });

  onSubTypeChange();
}

function onSubTypeChange() {
  const loanType = document.getElementById("loan_type").value;
  const subType = document.getElementById("loan_subtype").value;
  const repayAmountGroup = document.getElementById("repayAmountGroup");
  const termGroup = document.getElementById("termGroup");
  const termInput = document.getElementById("term_in_years");

  const shouldShowRepayAmount =
    loanType === "Sofortkredit" && subType === "tilgung";
  const shouldShowTerm =
    loanType === "Baudarlehen" ||
    (loanType === "Sofortkredit" && subType !== "tilgung");

  repayAmountGroup.style.display = shouldShowRepayAmount ? "flex" : "none";
  termGroup.style.display = shouldShowTerm ? "flex" : "none";

  termInput.disabled = shouldShowRepayAmount;
  if (shouldShowRepayAmount) termInput.value = "";
}
