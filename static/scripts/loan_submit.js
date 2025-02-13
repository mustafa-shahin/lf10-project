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

  repayAmountGroup.style.display = "none";
  termGroup.style.display = "none";
  subTypeSelect.innerHTML = "";

  const IMMEDIATE_SUBTYPES = ["tilgung", "endfaellig", "annuitaet"];
  const BUILDING_SUBTYPES = ["annuitaet"];

  if (loanType === "immediate") {
    populateSelect(subTypeSelect, IMMEDIATE_SUBTYPES);
  } else if (loanType === "building") {
    populateSelect(subTypeSelect, BUILDING_SUBTYPES);
  }

  onSubTypeChange();
}

function onSubTypeChange() {
  const loanType = document.getElementById("loan_type").value;
  const subType = document.getElementById("loan_subtype").value;
  const repayAmountGroup = document.getElementById("repayAmountGroup");
  const termGroup = document.getElementById("termGroup");

  const shouldShowRepayAmount =
    loanType === "immediate" && subType === "tilgung";
  const shouldShowTerm =
    loanType === "building" ||
    (loanType === "immediate" && subType !== "tilgung");

  repayAmountGroup.style.display = shouldShowRepayAmount ? "flex" : "none";
  termGroup.style.display = shouldShowTerm ? "flex" : "none";
}
