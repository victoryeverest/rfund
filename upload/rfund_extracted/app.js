const naira = new Intl.NumberFormat("en-NG", {
  style: "currency",
  currency: "NGN",
  maximumFractionDigits: 0,
});

const tenureDays = {
  quarterly: 91,
  "bi-yearly": 182,
  yearly: 365,
};

const frequencyMultiplier = {
  daily: 1,
  weekly: 1 / 7,
  monthly: 1 / 30.4167,
};

const amountInput = document.querySelector("#amount");
const frequencyInput = document.querySelector("#frequency");
const tenureInput = document.querySelector("#tenure");
const payout = document.querySelector("#payout");
const payoutNote = document.querySelector("#payoutNote");
const paymentModal = document.querySelector("#paymentModal");
const paymentSummary = document.querySelector("#paymentSummary");
const paymentStatus = document.querySelector("#paymentStatus");

function getSavingsPlan() {
  const amount = Number(amountInput.value || 0);
  const frequency = frequencyInput.value;
  const tenure = tenureInput.value;
  const days = tenureDays[tenure];
  const paymentCount = Math.round(days * frequencyMultiplier[frequency]);
  return {
    amount,
    frequency,
    tenure,
    days,
    paymentCount,
    total: amount * paymentCount,
  };
}

function updateSavingsResult() {
  const plan = getSavingsPlan();
  payout.textContent = naira.format(plan.total);
  payoutNote.textContent = `Based on ${naira.format(plan.amount)} ${plan.frequency} for ${plan.days} days.`;
}

document.querySelector("#savingsForm").addEventListener("submit", (event) => {
  event.preventDefault();
  updateSavingsResult();
});

[amountInput, frequencyInput, tenureInput].forEach((control) => {
  control.addEventListener("input", updateSavingsResult);
});

document.querySelectorAll("[data-open-payment]").forEach((button) => {
  button.addEventListener("click", () => {
    const plan = getSavingsPlan();
    paymentSummary.textContent = `Contribution due: ${naira.format(plan.amount)} ${plan.frequency}. Estimated tenure payout: ${naira.format(plan.total)}.`;
    paymentStatus.textContent = "";
    paymentModal.showModal();
  });
});

document.querySelectorAll("[data-method]").forEach((button) => {
  button.addEventListener("click", () => {
    const method = button.dataset.method;
    if (!paymentModal.open) {
      paymentModal.showModal();
    }
    paymentStatus.textContent = `${method} selected. This button is ready to connect to a live payment provider.`;
  });
});

document.querySelector("#loanForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const application = {
    product: document.querySelector("#loanProduct").value,
    name: document.querySelector("#applicantName").value,
    phone: document.querySelector("#phone").value,
    amount: document.querySelector("#loanAmount").value,
    purpose: document.querySelector("#purpose").value,
    createdAt: new Date().toISOString(),
  };
  localStorage.setItem("rfundLoanApplication", JSON.stringify(application));
  document.querySelector("#loanStatus").textContent =
    "Application saved. An RFUND agent can review and verify this request.";
  event.target.reset();
});

document.querySelector("#joinForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const profile = {
    name: document.querySelector("#joinName").value,
    phone: document.querySelector("#joinPhone").value,
    interest: document.querySelector("#joinInterest").value,
    createdAt: new Date().toISOString(),
  };
  localStorage.setItem("rfundProfile", JSON.stringify(profile));
  document.querySelector("#joinStatus").textContent =
    "Profile created on this device. Backend account creation can be connected next.";
  event.target.reset();
});

updateSavingsResult();
