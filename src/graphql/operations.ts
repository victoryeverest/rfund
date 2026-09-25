/**
 * All GraphQL operations used by the web app (spec §144: real examples).
 * Money values are strings (exact decimals) — never float.
 */

import { gql } from "@apollo/client";

export const LOGIN_MUTATION = gql`
  mutation Login($input: LoginInput!) {
    login(input: $input) {
      accessToken
      refreshToken
      expiresInMinutes
      user { id phone firstName lastName roles }
    }
  }
`;

export const REGISTER_MUTATION = gql`
  mutation Register($input: RegisterInput!) {
    registerCustomer(input: $input) {
      accessToken
      refreshToken
      expiresInMinutes
      user { id phone firstName lastName }
    }
  }
`;

export const ME_QUERY = gql`
  query Me {
    me {
      id customerReference fullName firstName lastName phone email
      state lga community occupation status kycTier preferredLanguage
      dateOfBirth gender address
    }
    kycStatus { status level verifiedAt failureReason }
  }
`;

export const DASHBOARD_QUERY = gql`
  query Dashboard {
    dashboard {
      savings { totalSaved activePlans nextContributionDate nextContributionAmount }
      loan { loanId reference outstanding nextRepaymentDate nextRepaymentAmount status }
      goalsCount
      unreadNotifications
    }
    payments(first: 6) {
      items { id reference purpose amount status createdAt method }
    }
  }
`;

export const SAVINGS_PRODUCTS_QUERY = gql`
  query SavingsProducts {
    savingsProducts {
      code name description minContribution maxContribution
      allowedFrequencies payoutPolicy allowEarlyPayout
    }
  }
`;

export const SAVINGS_PLANS_QUERY = gql`
  query SavingsPlans($first: Int, $after: String) {
    savingsPlans(first: $first, after: $after) {
      items {
        id reference productCode productName amount frequency
        startDate endDate status totalContributed
        contributionCount contributionsPaid
        nextDue { dueDate amount status }
      }
      pageInfo { totalCount hasNextPage nextCursor }
    }
  }
`;

export const SAVINGS_PLAN_QUERY = gql`
  query SavingsPlan($id: ID!) {
    savingsPlan(id: $id) {
      id reference productCode productName amount frequency startDate endDate
      status totalContributed contributionCount contributionsPaid nextDue { dueDate amount status }
    }
    savingsSchedule(planId: $id, first: 50) {
      items { id sequence dueDate amount status paidAt paymentReference }
      pageInfo { totalCount hasNextPage nextCursor }
    }
  }
`;

export const SAVINGS_PROJECTION_QUERY = gql`
  query SavingsProjection($amount: String!, $frequency: String!, $startDate: String!, $endDate: String!) {
    savingsProjection(amount: $amount, frequency: $frequency, startDate: $startDate, endDate: $endDate) {
      contributionCount totalAmount firstDue lastDue
    }
  }
`;

export const CREATE_SAVINGS_PLAN_MUTATION = gql`
  mutation CreateSavingsPlan($input: CreateSavingsPlanInput!) {
    createSavingsPlan(input: $input) {
      id reference amount frequency startDate endDate status
    }
  }
`;

export const CANCEL_SAVINGS_PLAN_MUTATION = gql`
  mutation CancelSavingsPlan($planId: ID!) {
    cancelSavingsPlan(planId: $planId) { id status }
  }
`;

export const SAVINGS_GOALS_QUERY = gql`
  query SavingsGoals {
    savingsGoals(first: 50) {
      items {
        id name description targetAmount currentAmount targetDate
        contributionFrequency contributionAmount status progressPct
      }
      pageInfo { totalCount }
    }
  }
`;

export const CREATE_GOAL_MUTATION = gql`
  mutation CreateGoal($input: CreateGoalInput!) {
    createSavingsGoal(input: $input) { id name status progressPct }
  }
`;

export const DELETE_GOAL_MUTATION = gql`
  mutation DeleteGoal($goalId: ID!) {
    deleteSavingsGoal(goalId: $goalId)
  }
`;

export const PAYMENTS_QUERY = gql`
  query Payments($first: Int, $after: String, $status: String, $purpose: String) {
    payments(first: $first, after: $after, status: $status, purpose: $purpose) {
      items {
        id reference purpose amount currency status method provider
        providerReference createdAt completedAt
      }
      pageInfo { totalCount hasNextPage nextCursor }
    }
  }
`;

export const MAKE_PAYMENT_MUTATION = gql`
  mutation MakePayment($input: MakePaymentInput!) {
    makePayment(input: $input) {
      payment { id reference amount status provider }
      authorizationUrl
    }
  }
`;

export const VERIFY_PAYMENT_MUTATION = gql`
  mutation VerifyPayment($paymentId: ID!) {
    verifyPayment(paymentId: $paymentId) {
      id reference status amount completedAt
    }
  }
`;

export const LOAN_PRODUCTS_QUERY = gql`
  query LoanProducts {
    loanProducts {
      code name description minAmount maxAmount termValues
      repaymentFrequency interestMethod interestRate
    }
  }
`;

export const LOAN_ELIGIBILITY_QUERY = gql`
  query LoanEligibility($productCode: String!, $amount: String!, $termMonths: Int!) {
    loanEligibility(productCode: $productCode, amount: $amount, termMonths: $termMonths) {
      eligible reasons
    }
  }
`;

export const LOAN_APPLICATIONS_QUERY = gql`
  query LoanApplications {
    loanApplications(first: 20) {
      items {
        id reference productCode productName amountRequested termMonths
        purpose state submittedAt rejectionReason
        offer { amount interestRate termMonths totalRepayable firstPaymentDate expiresOn status }
        assessment { score decision factors { rule name score explanation } }
      }
      pageInfo { totalCount }
    }
  }
`;

export const APPLY_FOR_LOAN_MUTATION = gql`
  mutation ApplyForLoan($input: ApplyForLoanInput!) {
    applyForLoan(input: $input) { id reference state }
  }
`;

export const ACCEPT_LOAN_OFFER_MUTATION = gql`
  mutation AcceptOffer($applicationId: ID!) {
    acceptLoanOffer(applicationId: $applicationId) { id state }
  }
`;

export const LOANS_QUERY = gql`
  query Loans {
    loans(first: 20) {
      id reference productName principal interestRate termMonths
      outstandingPrincipal outstandingInterest outstandingFees
      totalOutstanding status disbursedAt
    }
  }
`;

export const LOAN_QUERY = gql`
  query Loan($id: ID!) {
    loan(id: $id) {
      id reference productName principal interestRate termMonths
      outstandingPrincipal outstandingInterest outstandingFees
      totalOutstanding status disbursedAt
    }
    repaymentSchedule(loanId: $id, first: 60) {
      items {
        sequence dueDate principalDue interestDue feesDue penaltyDue
        totalDue amountPaid status
      }
      pageInfo { totalCount hasNextPage nextCursor }
    }
  }
`;

export const UPDATE_PROFILE_MUTATION = gql`
  mutation UpdateProfile($input: UpdateProfileInput!) {
    updateProfile(input: $input) {
      id firstName lastName email state lga community occupation preferredLanguage
    }
  }
`;

export const SUBMIT_KYC_MUTATION = gql`
  mutation SubmitKYC($input: SubmitKYCInput!) {
    submitKyc(input: $input) { status level verifiedAt failureReason }
  }
`;

export const SUPPORT_TICKETS_QUERY = gql`
  query SupportTickets {
    supportTickets(first: 20) {
      items { id reference category subject status priority createdAt messageCount }
      pageInfo { totalCount }
    }
  }
`;

export const CREATE_TICKET_MUTATION = gql`
  mutation CreateTicket($input: CreateTicketInput!) {
    createSupportTicket(input: $input) { id reference status }
  }
`;

export const REPLY_TICKET_MUTATION = gql`
  mutation ReplyTicket($input: ReplyTicketInput!) {
    replySupportTicket(input: $input) { id status }
  }
`;

// ---- Agent ----
export const AGENT_DASHBOARD_QUERY = gql`
  query AgentDashboard {
    agentDashboard {
      agent { id agentCode businessName status territoryCode territoryState floatBalance pendingSettlements }
      todayCollections
      todayTransactions
      availableFloat
    }
    agentTransactions(first: 20) {
      items { id reference txnType amount status customerName customerReference performedAt }
      pageInfo { totalCount hasNextPage nextCursor }
    }
  }
`;

export const AGENT_CUSTOMERS_QUERY = gql`
  query AgentCustomers($search: String, $first: Int, $after: String) {
    agentCustomers(search: $search, first: $first, after: $after) {
      items { id customerReference fullName phone state lga status kycTier }
      pageInfo { totalCount hasNextPage nextCursor }
    }
  }
`;

export const AGENT_CUSTOMER_PLANS_QUERY = gql`
  query AgentCustomerPlans($customerId: ID!) {
    agentCustomerPlans(customerId: $customerId) {
      id reference productName frequency amount status
    }
  }
`;

export const AGENT_CASH_COLLECTION_MUTATION = gql`
  mutation AgentCashCollection($input: AgentCashCollectionInput!) {
    agentCashCollection(input: $input) {
      id reference txnType amount status customerName performedAt
    }
  }
`;

export const AGENT_PAYOUT_MUTATION = gql`
  mutation AgentPayout($input: AgentPayoutInput!) {
    agentCustomerPayout(input: $input) {
      id reference txnType amount status customerName performedAt
    }
  }
`;

export const AGENT_SETTLEMENTS_QUERY = gql`
  query AgentSettlements {
    agentSettlements(first: 20) {
      id reference amount status requestedAt settledAt
    }
  }
`;

export const REQUEST_AGENT_SETTLEMENT_MUTATION = gql`
  mutation RequestSettlement($amount: String) {
    requestAgentSettlement(amount: $amount) { id reference amount status }
  }
`;

// ---- Admin ----
export const ADMIN_DASHBOARD_QUERY = gql`
  query AdminDashboard {
    adminDashboard {
      activeCustomers newCustomers7d savingsBalance activeSavingsPlans
      loanPortfolio activeLoans repaymentVolume30d interestIncome
      pendingKyc pendingLoanApplications paymentFailures24h
      reconciliationExceptions activeAgents agentCollectionsToday
      openFraudAlerts openSupportTickets
    }
  }
`;

export const ADMIN_LEDGER_QUERY = gql`
  query AdminLedger {
    adminLedgerAccounts { id code name type currency status balance lastPostedAt }
    adminLedgerTransactions(first: 30) {
      items {
        id reference transactionType status currency description
        externalReference postedAt createdAt
        entries { accountCode accountName direction amount currency }
      }
      pageInfo { totalCount hasNextPage nextCursor }
    }
  }
`;

export const ADMIN_CUSTOMERS_QUERY = gql`
  query AdminCustomers($search: String, $status: String, $first: Int, $after: String) {
    adminCustomers(search: $search, status: $status, first: $first, after: $after) {
      items {
        id customerReference fullName phone email state lga community
        status kycTier createdAt
      }
      pageInfo { totalCount hasNextPage nextCursor }
    }
  }
`;

export const ADMIN_KYC_QUEUE_QUERY = gql`
  query AdminKycQueue {
    adminKycQueue(first: 30) {
      items {
        id customerId customerName customerReference status level
        submittedDocType createdAt
      }
      pageInfo { totalCount hasNextPage nextCursor }
    }
  }
`;

export const ADMIN_REVIEW_KYC_MUTATION = gql`
  mutation ReviewKyc($input: ReviewKycInput!) {
    reviewKyc(input: $input)
  }
`;

export const ADMIN_LOAN_APPLICATIONS_QUERY = gql`
  query AdminLoanApplications($state: String) {
    adminLoanApplications(state: $state, first: 30) {
      items {
        id reference customerName customerReference productName amountRequested
        termMonths state riskScore riskDecision createdAt
      }
      pageInfo { totalCount hasNextPage nextCursor }
    }
  }
`;

export const ADMIN_DECIDE_LOAN_MUTATION = gql`
  mutation DecideLoan($input: LoanDecisionInput!) {
    decideLoanApplication(input: $input) { id reference state }
  }
`;

export const ADMIN_DISBURSE_LOAN_MUTATION = gql`
  mutation DisburseLoan($applicationId: ID!) {
    disburseLoan(applicationId: $applicationId) { id reference state }
  }
`;

export const ADMIN_PAYMENTS_QUERY = gql`
  query AdminPayments($status: String) {
    adminPayments(status: $status, first: 30) {
      items {
        id reference customerName purpose amount status provider
        providerReference ledgerReference createdAt
      }
      pageInfo { totalCount hasNextPage nextCursor }
    }
  }
`;

export const ADMIN_WEBHOOKS_QUERY = gql`
  query AdminWebhooks {
    adminWebhooks(first: 30) {
      items {
        id provider eventId eventType signatureValid processingStatus
        processingError receivedAt
      }
      pageInfo { totalCount hasNextPage nextCursor }
    }
  }
`;

export const ADMIN_RECONCILIATION_QUERY = gql`
  query AdminReconciliation {
    adminReconciliationRuns(first: 20) {
      id provider periodStart periodEnd status matchedCount exceptionCount startedAt
    }
    adminReconciliationExceptions(first: 30) {
      id itemStatus internalReference providerReference
      internalAmount providerAmount reason resolution resolved
    }
  }
`;

export const ADMIN_RUN_RECONCILIATION_MUTATION = gql`
  mutation RunReconciliation($provider: String) {
    runReconciliation(provider: $provider) {
      id provider status matchedCount exceptionCount
    }
  }
`;

export const ADMIN_RESOLVE_EXCEPTION_MUTATION = gql`
  mutation ResolveException($input: ResolveReconciliationInput!) {
    resolveReconciliationException(input: $input)
  }
`;

export const ADMIN_AGENTS_QUERY = gql`
  query AdminAgents {
    adminAgents(first: 30) {
      items { id agentCode businessName phone status territoryCode territoryState floatBalance createdAt }
      pageInfo { totalCount hasNextPage nextCursor }
    }
    adminAgentSettlements(first: 30) {
      id reference agentCode amount status requestedAt settledAt
    }
  }
`;

export const ADMIN_SET_AGENT_STATUS_MUTATION = gql`
  mutation SetAgentStatus($agentId: ID!, $status: String!, $reason: String) {
    setAgentStatus(agentId: $agentId, status: $status, reason: $reason)
  }
`;

export const ADMIN_APPROVE_SETTLEMENT_MUTATION = gql`
  mutation ApproveSettlement($settlementId: ID!) {
    approveAgentSettlement(settlementId: $settlementId)
  }
`;

export const ADMIN_FRAUD_ALERTS_QUERY = gql`
  query AdminFraudAlerts {
    adminFraudAlerts(first: 30) {
      items { id ruleCode resourceType resourceId severity status details createdAt }
      pageInfo { totalCount hasNextPage nextCursor }
    }
  }
`;

export const ADMIN_REVIEW_FRAUD_MUTATION = gql`
  mutation ReviewFraud($input: ReviewFraudAlertInput!) {
    reviewFraudAlert(input: $input)
  }
`;

export const ADMIN_AUDIT_QUERY = gql`
  query AdminAudit($resourceType: String) {
    adminAuditEvents(resourceType: $resourceType, first: 50) {
      items {
        id actorLabel action resourceType resourceId reason ipAddress occurredAt
      }
      pageInfo { totalCount hasNextPage nextCursor }
    }
  }
`;

export const ADMIN_SUPPORT_QUERY = gql`
  query AdminSupport($status: String) {
    adminSupportTickets(status: $status, first: 30) {
      items {
        id reference customerName category subject status priority
        assigneeName createdAt
      }
      pageInfo { totalCount hasNextPage nextCursor }
    }
  }
`;

export const ADMIN_REPORT_QUERY = gql`
  query AdminReport($reportType: String!) {
    adminReport(reportType: $reportType)
  }
`;

export const ADMIN_REVERSE_TRANSACTION_MUTATION = gql`
  mutation ReverseTransaction($transactionId: ID!, $reason: String!) {
    reverseLedgerTransaction(transactionId: $transactionId, reason: $reason) {
      id reference transactionType status
    }
  }
`;

export const NOTIFICATIONS_QUERY = gql`
  query Notifications($first: Int) {
    notifications(first: $first) {
      items { id eventCode label amount reference dispatched createdAt }
      totalCount
    }
  }
`;

export const REJECT_LOAN_OFFER_MUTATION = gql`
  mutation RejectOffer($applicationId: ID!) {
    rejectLoanOffer(applicationId: $applicationId) { id reference state }
  }
`;

export const UPDATE_GOAL_MUTATION = gql`
  mutation UpdateGoal($goalId: ID!, $input: UpdateGoalInput!) {
    updateSavingsGoal(goalId: $goalId, input: $input) {
      id name description targetAmount targetDate contributionFrequency contributionAmount
    }
  }
`;

export const ADMIN_SET_CUSTOMER_STATUS_MUTATION = gql`
  mutation SetCustomerStatus($customerId: ID!, $status: String!, $reason: String) {
    setCustomerStatus(customerId: $customerId, status: $status, reason: $reason)
  }
`;

export const REQUEST_OTP_MUTATION = gql`
  mutation RequestOtp($phone: String!, $purpose: String!) {
    requestOtp(phone: $phone, purpose: $purpose) { sent devCode }
  }
`;

export const LOGIN_WITH_OTP_MUTATION = gql`
  mutation LoginWithOtp($phone: String!, $code: String!) {
    loginWithOtp(phone: $phone, code: $code) {
      accessToken
      refreshToken
      expiresInMinutes
      user { id phone firstName lastName roles }
    }
  }
`;
