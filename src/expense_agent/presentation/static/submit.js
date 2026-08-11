"use strict";

const translations = {
  en: {
    documentTitle: "Expense Agent · Submit reimbursement",
    skipToForm: "Skip to reimbursement form",
    brandSubtitle: "Reimbursement portal",
    workspaceLabel: "Current workspace",
    newRequestNav: "New request",
    language: "Language",
    authenticatedAccount: "Authenticated account",
    signedInAs: "Signed in as",
    loadingIdentity: "Loading identity…",
    accountRoles: "Account roles",
    heroEyebrow: "Protected financial workflow",
    pageTitle: "Submit a reimbursement with confidence.",
    pageDescription: "Attach the original receipt, record the claim, and keep the request ID to follow every outcome.",
    workflowProtections: "Workflow protections",
    traceableTitle: "Traceable by design",
    traceableCopy: "Identity, evidence, policy route, and review decisions stay linked to one request.",
    checkingSession: "Checking your secure session…",
    checkingSessionHint: "Your identity is supplied by the authenticated service.",
    sessionErrorTitle: "We could not open your portal",
    sessionErrorMessage: "Sign in with an authorized account and try again.",
    sessionExpired: "Your session is no longer valid. Sign in again and retry.",
    accessDenied: "This account is not authorized to submit reimbursements.",
    tryAgain: "Try again",
    submissionSteps: "Submission steps",
    stepDetails: "Claim details",
    stepEvidence: "Evidence upload",
    stepResult: "Result",
    formEyebrow: "New reimbursement",
    formTitle: "Tell us about this expense",
    requiredFields: "Required fields",
    claimInformation: "Claim information",
    requestId: "Request ID",
    generateNewId: "Generate new ID",
    requestIdHelp: "Use this exact ID later to find the request across every status.",
    submittedBy: "Submitted by",
    verifiedIdentity: "Verified session identity · cannot be edited",
    claimedAmount: "Claimed amount",
    amountPlaceholder: "0.00",
    amountHelp: "Enter an exact BRL amount with up to two decimal places.",
    category: "Category",
    chooseCategory: "Choose a category",
    categoryMeals: "Meals",
    categoryClientMeal: "Client meal",
    categoryLodging: "Lodging",
    categoryTransport: "Transport",
    categoryOfficeSupplies: "Office supplies",
    categoryOther: "Other",
    originalReceipt: "Original receipt",
    chooseReceipt: "Choose one receipt file",
    receiptFormats: "JPEG, PNG, or PDF. The original bytes are preserved for traceability.",
    browseFile: "Browse file",
    fileSelected: "{name} · {size}",
    unsupportedFile: "Choose exactly one JPEG, PNG, or PDF file.",
    ocrAssessmentInput: "OCR text — assessment input",
    assessmentOnly: "Assessment only",
    ocrPlaceholder: "Paste the complete OCR output here",
    ocrAssessmentHelp: "This executable receives text already produced by OCR; it does not derive text from the uploaded file yet. The field is preserved as original evidence and must not authorize real payments.",
    submissionNotice: "Submitting links your identity, exact file, claim, and processing trace.",
    submitRequest: "Submit reimbursement",
    uploadingEvidence: "Uploading evidence…",
    processingRequest: "Processing request…",
    invalidRequestId: "Enter a valid request ID using letters, numbers, periods, underscores, colons, or hyphens.",
    invalidAmount: "Enter a positive exact amount with no more than two decimal places.",
    missingFile: "Choose exactly one supported original receipt.",
    missingOcr: "Paste the OCR text used as assessment input.",
    submissionFailed: "The reimbursement could not be submitted. Review the fields and try again.",
    uploadTooLarge: "The receipt exceeds the configured file-size limit.",
    uploadUnsupported: "The receipt bytes do not match a supported JPEG, PNG, or PDF.",
    uploadUnavailable: "Secure receipt upload is temporarily unavailable.",
    requestConflict: "This request ID already belongs to different information. Generate a new ID or look up the existing request.",
    invalidSubmission: "One or more claim fields are invalid. Review the values and try again.",
    serviceUnavailable: "The service is temporarily unavailable. Try again shortly.",
    networkError: "The service could not be reached. Your existing request ID can be used to check whether submission completed.",
    requestTracking: "Request tracking",
    trackerEyebrow: "Already submitted?",
    trackerTitle: "Track any request by exact ID",
    trackerDescription: "This direct lookup searches the authorized database across pending, approved, and rejected states.",
    requestIdPlaceholder: "REQ-20260811-XXXXXXXX",
    findRequest: "Find request",
    findingRequest: "Finding request…",
    requestNotFound: "No authorized request was found with that exact ID.",
    lookupFailed: "The request status could not be loaded. Try again.",
    privacyTitle: "Your evidence stays protected",
    privacyCopy: "The portal does not keep credentials, receipt data, or tokens in browser storage.",
    requestLocated: "Request located",
    requestSubmitted: "Request submitted",
    resultTitle: "Your reimbursement status",
    submittedAt: "Submitted at",
    policyRoute: "Policy route",
    extractionStatus: "Extraction status",
    explanationTitle: "Outcome and explanation",
    explanationCopy: "Messages below are rendered as text and keep their original audit wording.",
    submitAnother: "Submit another reimbursement",
    refreshStatus: "Refresh status",
    refreshingStatus: "Refreshing…",
    requestCreated: "Request {id} was recorded and processed successfully.",
    requestReplayed: "The existing request {id} was safely returned without duplicate processing.",
    requestFound: "This is the latest retained state for request {id}.",
    statusReceived: "Received",
    statusProcessing: "Processing",
    statusAutoApproved: "Automatically approved",
    statusPendingReview: "Pending human review",
    statusApprovedAfterReview: "Approved after review",
    statusRejected: "Rejected",
    guidanceReceived: "The request was received and is waiting for processing.",
    guidanceProcessing: "Evidence processing is in progress. Refresh this status shortly.",
    guidanceAutoApproved: "The deterministic policy approved this reimbursement automatically.",
    guidancePendingReview: "A qualified reviewer must make the final decision. No action is required from you now.",
    guidanceApprovedAfterReview: "A reviewer approved this reimbursement and recorded the rationale.",
    guidanceRejected: "This reimbursement was rejected. Review the recorded explanation below.",
    routeAutoApproved: "Automatic approval",
    routeHumanReview: "Human review",
    routeRejected: "Policy rejection",
    extractionSucceeded: "Succeeded",
    extractionFailed: "Failed",
    extractionPending: "Pending",
    humanDecisionReason: "Reviewer rationale",
    automatedReason: "Policy reason",
    detectedProblem: "Detected issue",
    noReasons: "No additional explanation was recorded for this state.",
    notAvailable: "Not available",
    roleSubmitter: "Submitter",
    roleReviewer: "Reviewer",
    roleAuditor: "Auditor",
    roleAdmin: "Administrator",
    resultUpdated: "Request status updated.",
    newRequestReady: "A new request form is ready.",
    bytes: "{count} bytes",
  },
  "pt-BR": {
    documentTitle: "Expense Agent · Solicitar reembolso",
    skipToForm: "Ir para o formulário de reembolso",
    brandSubtitle: "Portal de reembolsos",
    workspaceLabel: "Área atual",
    newRequestNav: "Nova solicitação",
    language: "Idioma",
    authenticatedAccount: "Conta autenticada",
    signedInAs: "Conectado como",
    loadingIdentity: "Carregando identidade…",
    accountRoles: "Perfis da conta",
    heroEyebrow: "Fluxo financeiro protegido",
    pageTitle: "Solicite um reembolso com confiança.",
    pageDescription: "Anexe o comprovante original, registre a despesa e guarde o ID para acompanhar qualquer resultado.",
    workflowProtections: "Proteções do fluxo",
    traceableTitle: "Rastreável desde o início",
    traceableCopy: "Identidade, evidência, rota da política e decisões ficam ligadas a uma única solicitação.",
    checkingSession: "Verificando sua sessão segura…",
    checkingSessionHint: "Sua identidade é fornecida pelo serviço autenticado.",
    sessionErrorTitle: "Não foi possível abrir seu portal",
    sessionErrorMessage: "Entre com uma conta autorizada e tente novamente.",
    sessionExpired: "Sua sessão não é mais válida. Entre novamente e tente outra vez.",
    accessDenied: "Esta conta não tem autorização para solicitar reembolsos.",
    tryAgain: "Tentar novamente",
    submissionSteps: "Etapas do envio",
    stepDetails: "Dados da despesa",
    stepEvidence: "Envio da evidência",
    stepResult: "Resultado",
    formEyebrow: "Novo reembolso",
    formTitle: "Conte sobre esta despesa",
    requiredFields: "Campos obrigatórios",
    claimInformation: "Informações da solicitação",
    requestId: "ID da solicitação",
    generateNewId: "Gerar novo ID",
    requestIdHelp: "Use este ID exato depois para localizar a solicitação em qualquer status.",
    submittedBy: "Solicitado por",
    verifiedIdentity: "Identidade verificada da sessão · não pode ser editada",
    claimedAmount: "Valor solicitado",
    amountPlaceholder: "0,00",
    amountHelp: "Informe um valor exato em BRL com no máximo duas casas decimais.",
    category: "Categoria",
    chooseCategory: "Escolha uma categoria",
    categoryMeals: "Refeições",
    categoryClientMeal: "Refeição com cliente",
    categoryLodging: "Hospedagem",
    categoryTransport: "Transporte",
    categoryOfficeSupplies: "Materiais de escritório",
    categoryOther: "Outro",
    originalReceipt: "Comprovante original",
    chooseReceipt: "Escolha um único comprovante",
    receiptFormats: "JPEG, PNG ou PDF. Os bytes originais são preservados para rastreabilidade.",
    browseFile: "Selecionar arquivo",
    fileSelected: "{name} · {size}",
    unsupportedFile: "Escolha exatamente um arquivo JPEG, PNG ou PDF.",
    ocrAssessmentInput: "Texto OCR — entrada do assessment",
    assessmentOnly: "Somente assessment",
    ocrPlaceholder: "Cole aqui a saída completa do OCR",
    ocrAssessmentHelp: "Este executável recebe um texto já produzido por OCR; ele ainda não extrai o texto do arquivo enviado. O campo é preservado como evidência original e não deve autorizar pagamentos reais.",
    submissionNotice: "O envio vincula sua identidade, arquivo exato, solicitação e trilha de processamento.",
    submitRequest: "Enviar reembolso",
    uploadingEvidence: "Enviando evidência…",
    processingRequest: "Processando solicitação…",
    invalidRequestId: "Informe um ID válido usando letras, números, pontos, sublinhados, dois-pontos ou hífens.",
    invalidAmount: "Informe um valor exato positivo com no máximo duas casas decimais.",
    missingFile: "Escolha exatamente um comprovante original compatível.",
    missingOcr: "Cole o texto OCR usado como entrada do assessment.",
    submissionFailed: "Não foi possível enviar o reembolso. Revise os campos e tente novamente.",
    uploadTooLarge: "O comprovante ultrapassa o limite de tamanho configurado.",
    uploadUnsupported: "Os bytes do comprovante não correspondem a JPEG, PNG ou PDF compatível.",
    uploadUnavailable: "O envio seguro de comprovantes está temporariamente indisponível.",
    requestConflict: "Este ID já pertence a informações diferentes. Gere um novo ID ou consulte a solicitação existente.",
    invalidSubmission: "Um ou mais dados da despesa são inválidos. Revise os valores e tente novamente.",
    serviceUnavailable: "O serviço está temporariamente indisponível. Tente novamente em instantes.",
    networkError: "Não foi possível acessar o serviço. Use o ID atual para verificar se o envio foi concluído.",
    requestTracking: "Acompanhamento de solicitação",
    trackerEyebrow: "Já enviou?",
    trackerTitle: "Acompanhe qualquer solicitação pelo ID exato",
    trackerDescription: "A consulta direta pesquisa a base autorizada nos estados pendente, aprovado e rejeitado.",
    requestIdPlaceholder: "REQ-20260811-XXXXXXXX",
    findRequest: "Buscar solicitação",
    findingRequest: "Buscando solicitação…",
    requestNotFound: "Nenhuma solicitação autorizada foi encontrada com esse ID exato.",
    lookupFailed: "Não foi possível carregar o status. Tente novamente.",
    privacyTitle: "Sua evidência permanece protegida",
    privacyCopy: "O portal não guarda credenciais, dados do comprovante ou tokens no armazenamento do navegador.",
    requestLocated: "Solicitação localizada",
    requestSubmitted: "Solicitação enviada",
    resultTitle: "Status do seu reembolso",
    submittedAt: "Enviado em",
    policyRoute: "Rota da política",
    extractionStatus: "Status da extração",
    explanationTitle: "Resultado e explicação",
    explanationCopy: "As mensagens abaixo são renderizadas como texto e mantêm a redação original da auditoria.",
    submitAnother: "Enviar outro reembolso",
    refreshStatus: "Atualizar status",
    refreshingStatus: "Atualizando…",
    requestCreated: "A solicitação {id} foi registrada e processada com sucesso.",
    requestReplayed: "A solicitação existente {id} foi retornada com segurança, sem processamento duplicado.",
    requestFound: "Este é o estado mais recente armazenado para a solicitação {id}.",
    statusReceived: "Recebido",
    statusProcessing: "Em processamento",
    statusAutoApproved: "Aprovado automaticamente",
    statusPendingReview: "Aguardando revisão humana",
    statusApprovedAfterReview: "Aprovado após revisão",
    statusRejected: "Rejeitado",
    guidanceReceived: "A solicitação foi recebida e aguarda processamento.",
    guidanceProcessing: "O processamento da evidência está em andamento. Atualize o status em instantes.",
    guidanceAutoApproved: "A política determinística aprovou este reembolso automaticamente.",
    guidancePendingReview: "Um revisor qualificado deve tomar a decisão final. Nenhuma ação sua é necessária agora.",
    guidanceApprovedAfterReview: "Um revisor aprovou este reembolso e registrou a justificativa.",
    guidanceRejected: "Este reembolso foi rejeitado. Consulte a explicação registrada abaixo.",
    routeAutoApproved: "Aprovação automática",
    routeHumanReview: "Revisão humana",
    routeRejected: "Rejeição por política",
    extractionSucceeded: "Concluída",
    extractionFailed: "Falhou",
    extractionPending: "Pendente",
    humanDecisionReason: "Justificativa do revisor",
    automatedReason: "Motivo da política",
    detectedProblem: "Problema detectado",
    noReasons: "Nenhuma explicação adicional foi registrada para este estado.",
    notAvailable: "Não disponível",
    roleSubmitter: "Solicitante",
    roleReviewer: "Revisor",
    roleAuditor: "Auditor",
    roleAdmin: "Administrador",
    resultUpdated: "Status da solicitação atualizado.",
    newRequestReady: "Um novo formulário está pronto.",
    bytes: "{count} bytes",
  },
  es: {
    documentTitle: "Expense Agent · Solicitar reembolso",
    skipToForm: "Ir al formulario de reembolso",
    brandSubtitle: "Portal de reembolsos",
    workspaceLabel: "Espacio actual",
    newRequestNav: "Nueva solicitud",
    language: "Idioma",
    authenticatedAccount: "Cuenta autenticada",
    signedInAs: "Sesión iniciada como",
    loadingIdentity: "Cargando identidad…",
    accountRoles: "Roles de la cuenta",
    heroEyebrow: "Flujo financiero protegido",
    pageTitle: "Solicita un reembolso con confianza.",
    pageDescription: "Adjunta el comprobante original, registra el gasto y conserva el ID para seguir cualquier resultado.",
    workflowProtections: "Protecciones del flujo",
    traceableTitle: "Trazable desde el diseño",
    traceableCopy: "Identidad, evidencia, ruta de política y decisiones quedan vinculadas a una sola solicitud.",
    checkingSession: "Verificando tu sesión segura…",
    checkingSessionHint: "Tu identidad es proporcionada por el servicio autenticado.",
    sessionErrorTitle: "No pudimos abrir tu portal",
    sessionErrorMessage: "Inicia sesión con una cuenta autorizada e inténtalo de nuevo.",
    sessionExpired: "Tu sesión ya no es válida. Inicia sesión de nuevo y vuelve a intentarlo.",
    accessDenied: "Esta cuenta no está autorizada para solicitar reembolsos.",
    tryAgain: "Intentar de nuevo",
    submissionSteps: "Pasos del envío",
    stepDetails: "Datos del gasto",
    stepEvidence: "Carga de evidencia",
    stepResult: "Resultado",
    formEyebrow: "Nuevo reembolso",
    formTitle: "Cuéntanos sobre este gasto",
    requiredFields: "Campos obligatorios",
    claimInformation: "Información de la solicitud",
    requestId: "ID de solicitud",
    generateNewId: "Generar nuevo ID",
    requestIdHelp: "Usa este ID exacto después para encontrar la solicitud en cualquier estado.",
    submittedBy: "Solicitado por",
    verifiedIdentity: "Identidad verificada de la sesión · no se puede editar",
    claimedAmount: "Importe solicitado",
    amountPlaceholder: "0,00",
    amountHelp: "Ingresa un importe BRL exacto con hasta dos decimales.",
    category: "Categoría",
    chooseCategory: "Elige una categoría",
    categoryMeals: "Comidas",
    categoryClientMeal: "Comida con cliente",
    categoryLodging: "Alojamiento",
    categoryTransport: "Transporte",
    categoryOfficeSupplies: "Material de oficina",
    categoryOther: "Otro",
    originalReceipt: "Comprobante original",
    chooseReceipt: "Elige un solo comprobante",
    receiptFormats: "JPEG, PNG o PDF. Los bytes originales se preservan para trazabilidad.",
    browseFile: "Seleccionar archivo",
    fileSelected: "{name} · {size}",
    unsupportedFile: "Elige exactamente un archivo JPEG, PNG o PDF.",
    ocrAssessmentInput: "Texto OCR — entrada del assessment",
    assessmentOnly: "Solo assessment",
    ocrPlaceholder: "Pega aquí la salida completa del OCR",
    ocrAssessmentHelp: "Este ejecutable recibe texto ya producido por OCR; todavía no extrae texto del archivo cargado. El campo se conserva como evidencia original y no debe autorizar pagos reales.",
    submissionNotice: "El envío vincula tu identidad, archivo exacto, solicitud y traza de procesamiento.",
    submitRequest: "Enviar reembolso",
    uploadingEvidence: "Cargando evidencia…",
    processingRequest: "Procesando solicitud…",
    invalidRequestId: "Ingresa un ID válido con letras, números, puntos, guiones bajos, dos puntos o guiones.",
    invalidAmount: "Ingresa un importe exacto positivo con no más de dos decimales.",
    missingFile: "Elige exactamente un comprobante original compatible.",
    missingOcr: "Pega el texto OCR usado como entrada del assessment.",
    submissionFailed: "No se pudo enviar el reembolso. Revisa los campos e inténtalo de nuevo.",
    uploadTooLarge: "El comprobante supera el límite de tamaño configurado.",
    uploadUnsupported: "Los bytes del comprobante no corresponden a un JPEG, PNG o PDF compatible.",
    uploadUnavailable: "La carga segura de comprobantes no está disponible temporalmente.",
    requestConflict: "Este ID ya pertenece a información diferente. Genera un ID nuevo o consulta la solicitud existente.",
    invalidSubmission: "Uno o más datos del gasto no son válidos. Revisa los valores e inténtalo de nuevo.",
    serviceUnavailable: "El servicio no está disponible temporalmente. Inténtalo de nuevo en breve.",
    networkError: "No se pudo acceder al servicio. Usa el ID actual para comprobar si el envío se completó.",
    requestTracking: "Seguimiento de solicitud",
    trackerEyebrow: "¿Ya la enviaste?",
    trackerTitle: "Sigue cualquier solicitud por su ID exacto",
    trackerDescription: "La consulta directa busca en la base autorizada entre estados pendientes, aprobados y rechazados.",
    requestIdPlaceholder: "REQ-20260811-XXXXXXXX",
    findRequest: "Buscar solicitud",
    findingRequest: "Buscando solicitud…",
    requestNotFound: "No se encontró una solicitud autorizada con ese ID exacto.",
    lookupFailed: "No se pudo cargar el estado. Inténtalo de nuevo.",
    privacyTitle: "Tu evidencia permanece protegida",
    privacyCopy: "El portal no guarda credenciales, datos del comprobante ni tokens en el almacenamiento del navegador.",
    requestLocated: "Solicitud localizada",
    requestSubmitted: "Solicitud enviada",
    resultTitle: "Estado de tu reembolso",
    submittedAt: "Enviado el",
    policyRoute: "Ruta de política",
    extractionStatus: "Estado de extracción",
    explanationTitle: "Resultado y explicación",
    explanationCopy: "Los mensajes siguientes se renderizan como texto y conservan la redacción original de auditoría.",
    submitAnother: "Enviar otro reembolso",
    refreshStatus: "Actualizar estado",
    refreshingStatus: "Actualizando…",
    requestCreated: "La solicitud {id} fue registrada y procesada correctamente.",
    requestReplayed: "La solicitud existente {id} se devolvió de forma segura, sin procesamiento duplicado.",
    requestFound: "Este es el estado más reciente conservado para la solicitud {id}.",
    statusReceived: "Recibida",
    statusProcessing: "En procesamiento",
    statusAutoApproved: "Aprobada automáticamente",
    statusPendingReview: "Pendiente de revisión humana",
    statusApprovedAfterReview: "Aprobada tras revisión",
    statusRejected: "Rechazada",
    guidanceReceived: "La solicitud fue recibida y está esperando procesamiento.",
    guidanceProcessing: "El procesamiento de la evidencia está en curso. Actualiza el estado en breve.",
    guidanceAutoApproved: "La política determinista aprobó este reembolso automáticamente.",
    guidancePendingReview: "Una persona revisora cualificada debe tomar la decisión final. No necesitas hacer nada ahora.",
    guidanceApprovedAfterReview: "Una persona revisora aprobó este reembolso y registró la justificación.",
    guidanceRejected: "Este reembolso fue rechazado. Consulta la explicación registrada a continuación.",
    routeAutoApproved: "Aprobación automática",
    routeHumanReview: "Revisión humana",
    routeRejected: "Rechazo por política",
    extractionSucceeded: "Completada",
    extractionFailed: "Falló",
    extractionPending: "Pendiente",
    humanDecisionReason: "Justificación de la revisión",
    automatedReason: "Motivo de la política",
    detectedProblem: "Problema detectado",
    noReasons: "No se registró una explicación adicional para este estado.",
    notAvailable: "No disponible",
    roleSubmitter: "Solicitante",
    roleReviewer: "Revisor",
    roleAuditor: "Auditor",
    roleAdmin: "Administrador",
    resultUpdated: "Estado de la solicitud actualizado.",
    newRequestReady: "Hay un nuevo formulario listo.",
    bytes: "{count} bytes",
  },
};

const supportedLanguages = Object.freeze(["pt-BR", "en", "es"]);
const allowedMediaTypes = new Set(["image/jpeg", "image/png", "application/pdf"]);
const allowedRoles = new Set(["submitter", "reviewer", "auditor", "admin"]);
const requestIdPattern = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const amountPattern = /^(?:0|[1-9][0-9]{0,15})(?:[.,][0-9]{1,2})?$/;
const attachmentReferencePattern = /^evidence:att_[0-9a-f]{32}$/;
const csrfPattern = /^[A-Za-z0-9._~-]{16,512}$/;

const statusKeys = Object.freeze({
  received: "statusReceived",
  processing: "statusProcessing",
  auto_approved: "statusAutoApproved",
  pending_review: "statusPendingReview",
  approved_after_review: "statusApprovedAfterReview",
  rejected: "statusRejected",
});

const guidanceKeys = Object.freeze({
  received: "guidanceReceived",
  processing: "guidanceProcessing",
  auto_approved: "guidanceAutoApproved",
  pending_review: "guidancePendingReview",
  approved_after_review: "guidanceApprovedAfterReview",
  rejected: "guidanceRejected",
});

const routeKeys = Object.freeze({
  auto_approved: "routeAutoApproved",
  human_review: "routeHumanReview",
  rejected: "routeRejected",
});

const extractionKeys = Object.freeze({
  succeeded: "extractionSucceeded",
  failed: "extractionFailed",
  pending: "extractionPending",
});

const roleKeys = Object.freeze({
  submitter: "roleSubmitter",
  reviewer: "roleReviewer",
  auditor: "roleAuditor",
  admin: "roleAdmin",
});

const categoryKeys = Object.freeze({
  meals: "categoryMeals",
  client_meal: "categoryClientMeal",
  lodging: "categoryLodging",
  transport: "categoryTransport",
  office_supplies: "categoryOfficeSupplies",
  other: "categoryOther",
});

const state = {
  language: "en",
  csrfToken: null,
  principal: null,
  roles: [],
  rolesDeclared: false,
  uploaded: null,
  submittedAt: null,
  currentResult: null,
  currentResultSource: "lookup",
  sessionErrorKey: null,
  submitting: false,
  tracking: false,
};

const elements = Object.fromEntries(
  [
    "language-select",
    "identity-avatar",
    "identity-name",
    "identity-roles",
    "session-loading",
    "session-error",
    "session-error-title",
    "session-error-message",
    "retry-session",
    "portal-content",
    "submission-form",
    "submission-fields",
    "request-id",
    "generate-request-id",
    "submitted-by",
    "claimed-amount",
    "claimed-category",
    "receipt-file",
    "file-title",
    "file-feedback",
    "raw-ocr-text",
    "submission-feedback",
    "submit-request",
    "submit-request-label",
    "tracking-form",
    "tracking-request-id",
    "track-request",
    "track-request-label",
    "tracking-feedback",
    "result-panel",
    "result-mark",
    "result-eyebrow",
    "result-guidance",
    "result-status",
    "result-request-id",
    "result-amount",
    "result-category",
    "result-submitted-at",
    "result-route",
    "result-extraction",
    "result-reasons",
    "start-another",
    "refresh-result",
    "toast",
    "announcer",
  ].map((id) => [id, document.getElementById(id)]),
);

let toastTimer = null;

function chooseLanguage() {
  const candidates = navigator.languages?.length ? navigator.languages : [navigator.language];
  for (const candidate of candidates) {
    const normalized = String(candidate || "").toLowerCase();
    if (normalized.startsWith("pt")) return "pt-BR";
    if (normalized.startsWith("es")) return "es";
    if (normalized.startsWith("en")) return "en";
  }
  return "en";
}

function t(key, variables = {}) {
  let text = translations[state.language]?.[key] ?? translations.en[key] ?? key;
  for (const [name, value] of Object.entries(variables)) {
    text = text.replaceAll(`{${name}}`, safeText(value, 200));
  }
  return text;
}

function applyTranslations() {
  document.documentElement.lang = state.language;
  document.title = t("documentTitle");
  for (const node of document.querySelectorAll("[data-i18n]")) {
    node.textContent = t(node.dataset.i18n);
  }
  for (const node of document.querySelectorAll("[data-i18n-placeholder]")) {
    node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
  }
  for (const node of document.querySelectorAll("[data-i18n-aria-label]")) {
    node.setAttribute("aria-label", t(node.dataset.i18nAriaLabel));
  }
  renderIdentityRoles();
  renderSelectedFile();
  if (state.sessionErrorKey) {
    elements["session-error-message"].textContent = t(state.sessionErrorKey);
  }
  if (state.currentResult) renderResult(state.currentResult, state.currentResultSource, false);
  syncBusyLabels();
}

function safeText(value, maxLength = 500) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "�")
    .slice(0, maxLength);
}

function initials(value) {
  const parts = safeText(value, 120).trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "--";
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase() ?? "").join("");
}

function clearNode(node) {
  while (node.firstChild) node.firstChild.remove();
}

function appendTextElement(parent, tag, value, className = null) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.textContent = safeText(value);
  parent.append(node);
  return node;
}

function announce(message) {
  elements.announcer.textContent = "";
  window.setTimeout(() => {
    elements.announcer.textContent = message;
  }, 20);
}

function showToast(message, isError = false) {
  window.clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.toggle("is-error", isError);
  elements.toast.hidden = false;
  toastTimer = window.setTimeout(() => {
    elements.toast.hidden = true;
  }, 5200);
}

class ApiError extends Error {
  constructor(status) {
    super(`HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
  }
}

async function api(path, options = {}) {
  const target = new URL(path, window.location.origin);
  if (target.origin !== window.location.origin) throw new Error("Cross-origin request blocked");
  const response = await fetch(target, {
    credentials: "same-origin",
    cache: "no-store",
    ...options,
  });
  const contentType = response.headers.get("content-type") ?? "";
  let body = null;
  if (contentType.includes("application/json")) {
    try {
      body = await response.json();
    } catch (_error) {
      body = null;
    }
  }
  if (!response.ok) throw new ApiError(response.status);
  return { body, response };
}

function normalizeRoles(candidate) {
  if (!Array.isArray(candidate)) return [];
  const normalized = candidate
    .filter((role) => typeof role === "string" && allowedRoles.has(role))
    .filter((role, index, roles) => roles.indexOf(role) === index);
  return normalized;
}

function validEmail(value) {
  return typeof value === "string"
    && value.length >= 3
    && value.length <= 320
    && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function validCsrfToken(value) {
  return typeof value === "string" && csrfPattern.test(value);
}

function renderIdentityRoles() {
  clearNode(elements["identity-roles"]);
  for (const role of state.roles) {
    appendTextElement(elements["identity-roles"], "span", t(roleKeys[role]), "role-chip");
  }
}

function showSessionError(messageKey) {
  state.sessionErrorKey = messageKey;
  elements["session-loading"].hidden = true;
  elements["portal-content"].hidden = true;
  elements["session-error"].hidden = false;
  elements["session-error-message"].textContent = t(messageKey);
}

async function loadSession() {
  state.sessionErrorKey = null;
  elements["session-error"].hidden = true;
  elements["portal-content"].hidden = true;
  elements["session-loading"].hidden = false;
  try {
    const { body } = await api("/api/session");
    const principal = body?.principal ?? body?.reviewer;
    if (!principal || !validEmail(principal.email) || !validCsrfToken(body?.csrf_token)) {
      throw new Error("Invalid session contract");
    }
    const roleCandidate = principal.roles ?? body?.roles;
    state.rolesDeclared = Array.isArray(roleCandidate);
    state.roles = normalizeRoles(roleCandidate);
    if (state.rolesDeclared && !state.roles.includes("submitter") && !state.roles.includes("admin")) {
      showSessionError("accessDenied");
      return;
    }
    state.principal = {
      email: principal.email,
      displayName: safeText(principal.display_name || principal.email, 160),
    };
    state.csrfToken = body.csrf_token;
    elements["identity-name"].textContent = state.principal.displayName;
    elements["identity-avatar"].textContent = initials(state.principal.displayName);
    elements["submitted-by"].textContent = state.principal.email;
    renderIdentityRoles();
    elements["session-loading"].hidden = true;
    elements["portal-content"].hidden = false;
    if (!elements["request-id"].value) generateRequestId();
  } catch (error) {
    showSessionError(error?.status === 401 ? "sessionExpired" : error?.status === 403 ? "accessDenied" : "sessionErrorMessage");
  }
}

function randomHex(length) {
  if (typeof crypto.randomUUID === "function") {
    return crypto.randomUUID().replaceAll("-", "").slice(0, length).toUpperCase();
  }
  const bytes = new Uint8Array(Math.ceil(length / 2));
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("").slice(0, length).toUpperCase();
}

function generateRequestId() {
  const day = new Date().toISOString().slice(0, 10).replaceAll("-", "");
  elements["request-id"].value = `REQ-${day}-${randomHex(8)}`;
  elements["request-id"].setCustomValidity("");
  state.submittedAt = null;
}

function normalizeRequestId(value) {
  const requestId = String(value ?? "").trim();
  return requestIdPattern.test(requestId) ? requestId : null;
}

function normalizeDecimalAmount(value) {
  const raw = String(value ?? "").trim();
  if (!amountPattern.test(raw)) return null;
  const normalized = raw.replace(",", ".");
  const [integer, fraction = ""] = normalized.split(".");
  const exact = `${integer}.${fraction.padEnd(2, "0")}`;
  if (/^0\.00$/.test(exact)) return null;
  return exact;
}

function fileSignature(file) {
  return [file.name, file.size, file.lastModified, file.type].join(":");
}

function safeAttachmentFilename(file) {
  const extension = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
  }[file.type];
  let base = String(file.name || "receipt").normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
  base = base.replace(/\.[^.]*$/, "").replace(/[^A-Za-z0-9 _()-]/g, "_").trim();
  base = base.replace(/^\.+/, "").slice(0, 180).replace(/[. ]+$/, "");
  return `${base || "receipt"}${extension}`;
}

function formatFileSize(size) {
  if (!Number.isSafeInteger(size) || size < 0) return t("notAvailable");
  if (size < 1024) return t("bytes", { count: size });
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function selectedFile() {
  const files = elements["receipt-file"].files;
  return files?.length === 1 ? files[0] : null;
}

function renderSelectedFile() {
  const file = selectedFile();
  const drop = document.querySelector(".file-drop");
  const valid = file && allowedMediaTypes.has(file.type) && file.size > 0;
  drop.classList.toggle("has-file", Boolean(valid));
  elements["file-feedback"].classList.toggle("is-error", Boolean(file && !valid));
  if (!file) {
    elements["file-title"].textContent = t("chooseReceipt");
    elements["file-feedback"].textContent = "";
    return;
  }
  elements["file-title"].textContent = safeText(file.name, 220);
  elements["file-feedback"].textContent = valid
    ? t("fileSelected", { name: file.name, size: formatFileSize(file.size) })
    : t("unsupportedFile");
}

function validateSubmission() {
  const requestId = normalizeRequestId(elements["request-id"].value);
  const amount = normalizeDecimalAmount(elements["claimed-amount"].value);
  const file = selectedFile();
  const ocrText = elements["raw-ocr-text"].value.trim();

  elements["request-id"].setCustomValidity(requestId ? "" : t("invalidRequestId"));
  elements["claimed-amount"].setCustomValidity(amount ? "" : t("invalidAmount"));
  elements["receipt-file"].setCustomValidity(
    file && allowedMediaTypes.has(file.type) && file.size > 0 ? "" : t("missingFile"),
  );
  elements["raw-ocr-text"].setCustomValidity(ocrText ? "" : t("missingOcr"));

  if (!elements["submission-form"].checkValidity()) {
    elements["submission-form"].reportValidity();
    return null;
  }
  return { requestId, amount, file, ocrText };
}

function setProgress(phase) {
  const order = ["details", "evidence", "result"];
  const current = order.indexOf(phase);
  for (const item of document.querySelectorAll(".progress li")) {
    const index = order.indexOf(item.dataset.phase);
    item.classList.toggle("is-active", index === current);
    item.classList.toggle("is-complete", index < current);
    if (index < current) item.querySelector("span").textContent = "✓";
    else item.querySelector("span").textContent = String(index + 1);
  }
}

function syncBusyLabels() {
  elements["submit-request-label"].textContent = t(
    state.submitting ? (state.uploaded ? "processingRequest" : "uploadingEvidence") : "submitRequest",
  );
  elements["track-request-label"].textContent = t(state.tracking ? "findingRequest" : "findRequest");
}

function setSubmissionBusy(busy) {
  state.submitting = busy;
  elements["submission-fields"].disabled = busy;
  elements["submit-request"].disabled = busy;
  elements["generate-request-id"].disabled = busy;
  syncBusyLabels();
}

function setTrackingBusy(busy) {
  state.tracking = busy;
  elements["tracking-request-id"].disabled = busy;
  elements["track-request"].disabled = busy;
  elements["refresh-result"].disabled = busy;
  syncBusyLabels();
}

function extractAttachmentReference(payload) {
  const reference = payload?.reference ?? payload?.attachment?.reference;
  if (typeof reference !== "string" || !attachmentReferencePattern.test(reference)) {
    throw new Error("Invalid attachment response");
  }
  return reference;
}

async function uploadReceipt(file) {
  const signature = fileSignature(file);
  if (state.uploaded?.signature === signature) return state.uploaded.reference;
  state.uploaded = null;
  setProgress("evidence");
  syncBusyLabels();
  const { body } = await api("/api/attachments", {
    method: "POST",
    headers: {
      "Accept": "application/json",
      "Content-Type": file.type,
      "X-Attachment-Filename": safeAttachmentFilename(file),
      "X-CSRF-Token": state.csrfToken,
    },
    // This is same-origin; the browser emits the protected Origin header itself.
    body: file,
  });
  const reference = extractAttachmentReference(body);
  state.uploaded = { signature, reference };
  return reference;
}

async function createRequest(values, reference) {
  if (!state.submittedAt) state.submittedAt = new Date().toISOString();
  syncBusyLabels();
  const payload = {
    request_id: values.requestId,
    submitted_by: state.principal.email,
    submitted_at: state.submittedAt,
    raw_ocr_text: values.ocrText,
    claimed_category: elements["claimed-category"].value,
    claimed_amount_brl: values.amount,
    attachments: [reference],
  };
  return api("/api/requests", {
    method: "POST",
    headers: {
      "Accept": "application/json",
      "Content-Type": "application/json",
      "X-CSRF-Token": state.csrfToken,
    },
    body: JSON.stringify(payload),
  });
}

function submissionErrorKey(error, stage) {
  if (!error?.status) return "networkError";
  if (error.status === 401) return "sessionExpired";
  if (error.status === 403) return "accessDenied";
  if (stage === "upload" && error.status === 413) return "uploadTooLarge";
  if (stage === "upload" && [415, 422].includes(error.status)) return "uploadUnsupported";
  if (stage === "upload" && [404, 409, 503].includes(error.status)) return "uploadUnavailable";
  if (error.status === 409) return "requestConflict";
  if (error.status === 415 || error.status === 422) return "invalidSubmission";
  if (error.status === 429 || error.status >= 500) return "serviceUnavailable";
  return "submissionFailed";
}

async function recoverAmbiguousSubmission(requestId) {
  try {
    const { body } = await api(`/api/requests/${encodeURIComponent(requestId)}`);
    if (body?.request_id === requestId) {
      renderResult(body, "lookup");
      return true;
    }
  } catch (_error) {
    return false;
  }
  return false;
}

async function submitReimbursement(event) {
  event.preventDefault();
  if (state.submitting || !state.principal || !state.csrfToken) return;
  elements["submission-feedback"].hidden = true;
  const values = validateSubmission();
  if (!values) return;
  let stage = "upload";
  setSubmissionBusy(true);
  try {
    const reference = await uploadReceipt(values.file);
    stage = "request";
    const { body } = await createRequest(values, reference);
    renderResult(body, body?.replayed ? "replay" : "submission");
    elements["tracking-request-id"].value = safeText(body?.request_id, 128);
  } catch (error) {
    if (stage === "request" && !error?.status && await recoverAmbiguousSubmission(values.requestId)) {
      showToast(t("resultUpdated"));
      return;
    }
    const message = t(submissionErrorKey(error, stage));
    elements["submission-feedback"].textContent = message;
    elements["submission-feedback"].hidden = false;
    showToast(message, true);
    setProgress(stage === "upload" ? "details" : "evidence");
  } finally {
    setSubmissionBusy(false);
  }
}

function knownCode(value, mapping) {
  return typeof value === "string" && Object.hasOwn(mapping, value) ? value : null;
}

function formatExactMoney(money) {
  const rawAmount = typeof money?.amount === "string" ? money.amount : null;
  const currency = typeof money?.currency === "string" ? safeText(money.currency, 8) : "BRL";
  if (!rawAmount || !/^[0-9]{1,18}(?:\.[0-9]{1,2})?$/.test(rawAmount)) return t("notAvailable");
  const [integer, fraction = ""] = rawAmount.split(".");
  const grouping = state.language === "en" ? "," : ".";
  const decimal = state.language === "en" ? "." : ",";
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, grouping);
  return `${currency} ${grouped}${decimal}${fraction.padEnd(2, "0")}`;
}

function formatDate(value) {
  if (typeof value !== "string" || value.length > 64) return t("notAvailable");
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return t("notAvailable");
  return new Intl.DateTimeFormat(state.language, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function translatedCategory(value) {
  if (typeof value !== "string") return t("notAvailable");
  return categoryKeys[value] ? t(categoryKeys[value]) : safeText(value.replaceAll("_", " "), 200);
}

function collectReasons(result) {
  const collected = [];
  const humanReason = result?.review?.human_decision?.reason;
  if (typeof humanReason === "string" && humanReason.trim()) {
    collected.push({ label: t("humanDecisionReason"), code: "HUMAN_DECISION", message: humanReason });
  }
  const automatedReasons = Array.isArray(result?.automated_decision?.reasons)
    ? result.automated_decision.reasons
    : [];
  for (const reason of automatedReasons.slice(0, 12)) {
    if (typeof reason?.message === "string" && reason.message.trim()) {
      collected.push({
        label: t("automatedReason"),
        code: safeText(reason.code || "POLICY", 100),
        message: reason.message,
      });
    }
  }
  const problems = Array.isArray(result?.problems) ? result.problems : [];
  for (const problem of problems.slice(0, 12)) {
    if (typeof problem?.message === "string" && problem.message.trim()) {
      collected.push({
        label: t("detectedProblem"),
        code: safeText(problem.code || "ISSUE", 100),
        message: problem.message,
      });
    }
  }
  const seen = new Set();
  return collected.filter((item) => {
    const fingerprint = `${item.label}\u0000${item.code}\u0000${item.message}`;
    if (seen.has(fingerprint)) return false;
    seen.add(fingerprint);
    return true;
  }).slice(0, 20);
}

function renderReasons(result) {
  clearNode(elements["result-reasons"]);
  const reasons = collectReasons(result);
  if (!reasons.length) {
    const item = document.createElement("li");
    appendTextElement(item, "span", t("noReasons"));
    elements["result-reasons"].append(item);
    return;
  }
  for (const reason of reasons) {
    const item = document.createElement("li");
    appendTextElement(item, "strong", `${reason.label} · ${safeText(reason.code, 100)}`);
    appendTextElement(item, "span", safeText(reason.message, 1000));
    elements["result-reasons"].append(item);
  }
}

function renderResult(result, source = "lookup", focus = true) {
  if (!result || typeof result.request_id !== "string") return;
  state.currentResult = result;
  state.currentResultSource = source;
  const requestId = safeText(result.request_id, 128);
  const status = knownCode(result.status, statusKeys);
  const route = knownCode(result?.automated_decision?.route, routeKeys);
  const extraction = knownCode(result?.extraction?.status, extractionKeys);

  elements["result-eyebrow"].textContent = t(source === "submission" || source === "replay" ? "requestSubmitted" : "requestLocated");
  elements["result-guidance"].textContent = t(
    source === "submission" ? "requestCreated" : source === "replay" ? "requestReplayed" : "requestFound",
    { id: requestId },
  );
  elements["result-status"].textContent = status ? t(statusKeys[status]) : t("notAvailable");
  elements["result-status"].removeAttribute("data-status");
  if (status) elements["result-status"].setAttribute("data-status", status);
  elements["result-request-id"].textContent = requestId;
  elements["result-amount"].textContent = formatExactMoney(result.claimed_amount);
  elements["result-category"].textContent = translatedCategory(result.claimed_category);
  elements["result-submitted-at"].textContent = formatDate(result.submitted_at);
  elements["result-route"].textContent = route ? t(routeKeys[route]) : t("notAvailable");
  elements["result-extraction"].textContent = extraction ? t(extractionKeys[extraction]) : t("notAvailable");
  elements["result-guidance"].textContent += ` ${status ? t(guidanceKeys[status]) : ""}`;

  elements["result-mark"].textContent = status === "rejected" ? "×" : status === "pending_review" || status === "processing" || status === "received" ? "…" : "✓";
  elements["result-mark"].classList.toggle("is-pending", ["received", "processing", "pending_review"].includes(status));
  elements["result-mark"].classList.toggle("is-rejected", status === "rejected");
  renderReasons(result);
  elements["result-panel"].hidden = false;
  elements["tracking-feedback"].hidden = true;
  setProgress("result");
  if (focus) {
    const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
    elements["result-panel"].scrollIntoView({ behavior, block: "start" });
    elements["result-panel"].focus({ preventScroll: true });
  }
  announce(elements["result-guidance"].textContent);
}

function lookupErrorKey(error) {
  if (error?.status === 401) return "sessionExpired";
  if (error?.status === 403) return "accessDenied";
  if (error?.status === 404) return "requestNotFound";
  if (error?.status === 429 || error?.status >= 500) return "serviceUnavailable";
  if (!error?.status) return "networkError";
  return "lookupFailed";
}

async function lookupRequest(requestId, { announceSuccess = false } = {}) {
  const normalized = normalizeRequestId(requestId);
  elements["tracking-request-id"].setCustomValidity(normalized ? "" : t("invalidRequestId"));
  if (!normalized) {
    elements["tracking-request-id"].reportValidity();
    return false;
  }
  elements["tracking-feedback"].hidden = true;
  setTrackingBusy(true);
  try {
    const { body } = await api(`/api/requests/${encodeURIComponent(normalized)}`);
    renderResult(body, "lookup");
    if (announceSuccess) showToast(t("resultUpdated"));
    return true;
  } catch (error) {
    const message = t(lookupErrorKey(error));
    elements["tracking-feedback"].textContent = message;
    elements["tracking-feedback"].hidden = false;
    showToast(message, true);
    return false;
  } finally {
    setTrackingBusy(false);
  }
}

function resetSubmission() {
  elements["submission-form"].reset();
  state.uploaded = null;
  state.submittedAt = null;
  state.currentResult = null;
  state.currentResultSource = "lookup";
  elements["submission-feedback"].hidden = true;
  elements["result-panel"].hidden = true;
  elements["submitted-by"].textContent = state.principal?.email ?? "--";
  generateRequestId();
  renderSelectedFile();
  setProgress("details");
  elements["request-id"].focus();
  showToast(t("newRequestReady"));
}

elements["language-select"].addEventListener("change", () => {
  if (!supportedLanguages.includes(elements["language-select"].value)) return;
  state.language = elements["language-select"].value;
  applyTranslations();
});

elements["retry-session"].addEventListener("click", loadSession);
elements["generate-request-id"].addEventListener("click", generateRequestId);
elements["receipt-file"].addEventListener("change", () => {
  state.uploaded = null;
  elements["receipt-file"].setCustomValidity("");
  renderSelectedFile();
});
elements["request-id"].addEventListener("input", () => {
  elements["request-id"].setCustomValidity("");
});
elements["claimed-amount"].addEventListener("input", () => {
  elements["claimed-amount"].setCustomValidity("");
});
elements["raw-ocr-text"].addEventListener("input", () => {
  elements["raw-ocr-text"].setCustomValidity("");
});
elements["submission-form"].addEventListener("submit", submitReimbursement);
elements["tracking-form"].addEventListener("submit", (event) => {
  event.preventDefault();
  if (!state.tracking) lookupRequest(elements["tracking-request-id"].value);
});
elements["refresh-result"].addEventListener("click", () => {
  if (state.currentResult?.request_id) lookupRequest(state.currentResult.request_id, { announceSuccess: true });
});
elements["start-another"].addEventListener("click", resetSubmission);

state.language = chooseLanguage();
elements["language-select"].value = state.language;
applyTranslations();
loadSession();
