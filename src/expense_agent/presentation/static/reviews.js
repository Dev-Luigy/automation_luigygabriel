const translations = {
  en: {
    documentTitle: "Expense Agent · Review operations",
    skipToWorklist: "Skip to review worklist",
    brandSubtitle: "Human review workspace",
    workspaceLabel: "Current workspace",
    reviewQueueNav: "Review queue",
    language: "Language",
    authenticatedReviewer: "Authenticated reviewer",
    signedInAs: "Signed in as",
    loadingIdentity: "Loading identity…",
    operationsEyebrow: "Financial operations",
    pageTitle: "Review operations",
    pageDescription: "Find the right case quickly, compare evidence, and record an accountable decision.",
    refresh: "Refresh",
    queueOverview: "Queue overview",
    totalPending: "Total pending",
    allPendingCases: "All pending cases",
    currentPageOnly: "Current page only",
    urgentPending: "Waiting over 24h",
    oldestFirstHint: "Prioritize the oldest cases",
    highValue: "High value",
    configuredThreshold: "Configured threshold",
    highValueAbove: "Above {amount}",
    amountMismatch: "Amount mismatch",
    claimedVsExtracted: "Claimed versus extracted",
    worklistEyebrow: "Operational worklist",
    pendingCases: "Pending cases",
    view: "View",
    tableView: "Table",
    cardView: "Cards",
    searchLabel: "Search pending cases",
    searchPlaceholder: "Request ID, submitter, or merchant",
    filters: "Filters",
    sortBy: "Sort by",
    sortOldest: "Waiting longest",
    sortNewest: "Recently pending",
    sortAmountDesc: "Highest amount",
    sortAmountAsc: "Lowest amount",
    sortSubmittedNewest: "Recently submitted",
    rows: "Rows",
    category: "Category",
    allCategoriesOrCode: "All categories or exact code",
    categoryClientMeal: "Client meal",
    categoryMeals: "Meals",
    categoryLodging: "Lodging",
    categoryTransport: "Transport",
    categoryOfficeSupplies: "Office supplies",
    categoryOther: "Other",
    problemType: "Problem type",
    allProblemsOrCode: "All problems or exact code",
    allProblems: "All problems",
    problemAmountMismatch: "Amount mismatch",
    problemTotalMismatch: "Total mismatch",
    problemCategoryMismatch: "Category mismatch",
    problemLowOcr: "Low OCR confidence",
    problemDuplicate: "Possible duplicate",
    problemPolicyEvidence: "Policy evidence required",
    problemMissingDate: "Receipt date missing",
    problemMissingMerchant: "Merchant missing",
    problemInvalidTaxId: "Invalid tax ID",
    claimedAmountRange: "Claimed amount",
    minimum: "Minimum",
    maximum: "Maximum",
    submittedRange: "Submitted date",
    from: "From",
    to: "To",
    pendingAge: "Pending age",
    anyAge: "Any age",
    ageUnder4h: "Under 4 hours",
    age4to24h: "4 to 24 hours",
    ageOver24h: "Over 24 hours",
    resetAll: "Reset all",
    applyFilters: "Apply filters",
    activeFilters: "Active filters",
    clearAll: "Clear all",
    loadingQueue: "Loading review queue…",
    loadingQueueHint: "This may take a moment for complex filters.",
    queueErrorTitle: "The queue could not be loaded",
    queueErrorMessage: "Check your connection and try again.",
    queueInvalidQuery: "One or more filters are invalid. Review the values and try again.",
    sessionExpired: "Your session is no longer valid. Sign in again and retry.",
    accessDenied: "You do not have permission to access this review queue.",
    serviceUnavailable: "The review service is temporarily unavailable. Try again shortly.",
    tryAgain: "Try again",
    queueClearTitle: "The queue is clear",
    queueClearMessage: "There are no reimbursements waiting for review.",
    noMatchesTitle: "No cases match these filters",
    noMatchesMessage: "Adjust or clear the current filters to broaden the result.",
    resetFilters: "Reset filters",
    queueTableCaption: "Pending reimbursements matching the current query",
    request: "Request",
    submitter: "Submitter",
    merchant: "Merchant",
    claimed: "Claimed",
    primaryProblem: "Primary problem",
    submitted: "Submitted",
    pendingSince: "Pending since",
    extractedValue: "Extracted: {amount}",
    status: "Status",
    actions: "Actions",
    openCase: "Open case {id}",
    previous: "Previous",
    next: "Next",
    page: "Page {number}",
    pageSummary: "{count} cases on this page",
    pageSummaryOne: "1 case on this page",
    reimbursement: "Reimbursement",
    reviewEvidence: "Review evidence",
    closeDetails: "Close case details",
    close: "Close",
    loadingDetails: "Loading case evidence…",
    detailErrorTitle: "Case details could not be loaded",
    detailErrorMessage: "Try opening the case again.",
    caseNotFound: "This case is no longer available in the review queue.",
    caseSections: "Case sections",
    comparison: "Comparison",
    problems: "Problems",
    evidence: "Evidence",
    rules: "Rules",
    businessTimeline: "Business timeline",
    businessTimelineEyebrow: "Immutable business history",
    businessTimelineHelp: "Business events are shown separately from the protected technical trace.",
    loadingTimeline: "Loading business timeline…",
    timelineErrorTitle: "The business timeline could not be loaded",
    timelineErrorMessage: "Try loading the business events again.",
    retryTimeline: "Retry timeline",
    timelineEmptyTitle: "No business events recorded",
    timelineEmptyMessage: "This case does not have events available to this reviewer.",
    loadMoreEvents: "Load more events",
    loadingMoreEvents: "Loading events…",
    timelineLoaded: "{count} business events loaded.",
    timelineLoadedOne: "1 business event loaded.",
    timelineEventEnqueued: "Sent to human review",
    timelineEventDecided: "Human decision recorded",
    timelineEventGeneric: "Business event",
    eventTypeCode: "Event type",
    eventIdentifier: "Event ID",
    eventActor: "Actor",
    eventCorrelation: "Correlation ID",
    eventStateChange: "State transition",
    eventOutcome: "Outcome",
    eventReasonOriginal: "Original rationale",
    eventRequestVersion: "Request version",
    eventPolicyVersion: "Policy version",
    eventRoute: "Automated route",
    eventDecisionId: "Decision ID",
    eventAutomatedDecisionId: "Automated decision ID",
    eventExtractionStatus: "Extraction status",
    eventAttachmentCount: "Attachment count",
    noTimelineDetails: "No additional business details were recorded.",
    decision: "Decision",
    claimSummary: "Claim summary",
    submittedBy: "Submitted by",
    policyVersion: "Policy version",
    attachmentCount: "Attachments",
    decisionSnapshot: "Decision snapshot",
    claimedExtractedComparison: "Claimed vs. extracted",
    comparisonHint: "Comparison indicators assist review; policy remains authoritative.",
    field: "Field",
    extracted: "Extracted",
    match: "Match",
    mismatch: "Mismatch",
    incomplete: "Incomplete",
    whyReview: "Why human judgment is needed",
    detectedProblems: "Detected problems",
    sourceEvidence: "Source evidence",
    ocrOutput: "OCR output",
    originalLanguage: "Original language",
    normalizedObject: "Normalized object",
    extractedReceipt: "Extracted receipt",
    deterministicPolicy: "Deterministic policy",
    ruleEvaluations: "Rule evaluations",
    rule: "Rule",
    version: "Version",
    result: "Result",
    explanation: "Explanation",
    originalFiles: "Original files",
    attachments: "Attachments",
    attachmentLimitation: "This assessment records file references only. Authorized preview and download are not implemented yet.",
    authoritativeAction: "Authoritative human action",
    recordDecision: "Record your decision",
    decisionAuditNotice: "Your authenticated identity, rationale, timestamp, and case version will be written to the immutable audit trail.",
    mandatoryRejectionNotice: "A mandatory rejection rule applies. This high-value case still requires human review, but it cannot be approved.",
    rationale: "Rationale",
    required: "required",
    rationalePlaceholder: "Explain the evidence and reasoning behind your decision.",
    rationaleHint: "Do not include passwords, tokens, or unrelated personal data.",
    rejectReimbursement: "Reject reimbursement",
    approveReimbursement: "Approve reimbursement",
    finalConfirmation: "Final confirmation",
    confirmDecision: "Confirm decision",
    immutableWarning: "This decision cannot be edited after it is recorded.",
    goBack: "Go back",
    confirmAndRecord: "Confirm and record",
    confirmApprove: "Confirm approval",
    confirmReject: "Confirm rejection",
    confirmApproveCopy: "You are about to approve {id}. This creates an immutable audit record.",
    confirmRejectCopy: "You are about to reject {id}. This creates an immutable audit record.",
    rationaleRequired: "A rationale is required before a decision can be recorded.",
    decisionRecorded: "Decision recorded. Audit event {eventId}.",
    caseChanged: "This case changed before your decision was recorded. The latest state has been loaded.",
    decisionFailed: "The decision could not be recorded. Review the case and try again.",
    receiptDate: "Receipt date",
    extractedTotal: "Extracted total",
    merchantName: "Merchant",
    taxId: "Tax ID",
    warnings: "Warnings",
    evidenceItems: "Evidence",
    noExplicitProblem: "No explicit problem",
    noAdditionalProblem: "No additional issue was recorded.",
    noRules: "No rule evaluation was recorded.",
    noAttachments: "No attachment reference was recorded.",
    noOcr: "No OCR text was recorded.",
    notAvailable: "Not available",
    none: "None",
    pendingReview: "Pending review",
    approvedAfterReview: "Approved after review",
    rejectedAfterReview: "Rejected after review",
    approved: "Approved",
    rejected: "Rejected",
    passed: "Passed",
    needsReview: "Review",
    ruleRejected: "Rejected",
    submittedAt: "Submitted {date}",
    lastUpdated: "Updated {date}",
    problemsCount: "{count} problems",
    oneProblem: "1 problem",
    noPrimaryProblem: "No primary problem",
    queueLoaded: "Review queue loaded with {count} cases on this page.",
    queueLoadedOne: "Review queue loaded with 1 case on this page.",
    tableViewActive: "Table view active.",
    cardViewActive: "Card view active.",
    filterSearch: "Search",
    filterCategory: "Category",
    filterProblem: "Problem",
    filterMinimum: "Minimum",
    filterMaximum: "Maximum",
    filterSubmittedFrom: "Submitted from",
    filterSubmittedTo: "Submitted to",
    filterAge: "Pending age",
    removeFilter: "Remove filter {filter}",
    invalidAmountRange: "The maximum amount must be greater than or equal to the minimum amount.",
    invalidDateRange: "The end date must be on or after the start date.",
    invalidAmount: "Use a non-negative amount with no more than two decimal places.",
  },
  "pt-BR": {
    documentTitle: "Expense Agent · Operações de revisão",
    skipToWorklist: "Ir para a fila de revisão",
    brandSubtitle: "Área de revisão humana",
    workspaceLabel: "Área atual",
    reviewQueueNav: "Fila de revisão",
    language: "Idioma",
    authenticatedReviewer: "Revisor autenticado",
    signedInAs: "Conectado como",
    loadingIdentity: "Carregando identidade…",
    operationsEyebrow: "Operações financeiras",
    pageTitle: "Operações de revisão",
    pageDescription: "Encontre o caso certo rapidamente, compare as evidências e registre uma decisão responsável.",
    refresh: "Atualizar",
    queueOverview: "Visão geral da fila",
    totalPending: "Total pendente",
    allPendingCases: "Todos os casos pendentes",
    currentPageOnly: "Somente a página atual",
    urgentPending: "Aguardando há mais de 24h",
    oldestFirstHint: "Priorize os casos mais antigos",
    highValue: "Alto valor",
    configuredThreshold: "Limite configurado",
    highValueAbove: "Acima de {amount}",
    amountMismatch: "Divergência de valor",
    claimedVsExtracted: "Declarado versus extraído",
    worklistEyebrow: "Fila operacional",
    pendingCases: "Casos pendentes",
    view: "Visualização",
    tableView: "Tabela",
    cardView: "Cards",
    searchLabel: "Buscar casos pendentes",
    searchPlaceholder: "ID da solicitação, solicitante ou estabelecimento",
    filters: "Filtros",
    sortBy: "Ordenar por",
    sortOldest: "Maior tempo de espera",
    sortNewest: "Pendente recentemente",
    sortAmountDesc: "Maior valor",
    sortAmountAsc: "Menor valor",
    sortSubmittedNewest: "Enviado recentemente",
    rows: "Linhas",
    category: "Categoria",
    allCategoriesOrCode: "Todas as categorias ou código exato",
    categoryClientMeal: "Refeição com cliente",
    categoryMeals: "Refeições",
    categoryLodging: "Hospedagem",
    categoryTransport: "Transporte",
    categoryOfficeSupplies: "Material de escritório",
    categoryOther: "Outros",
    problemType: "Tipo de problema",
    allProblemsOrCode: "Todos os problemas ou código exato",
    allProblems: "Todos os problemas",
    problemAmountMismatch: "Divergência de valor",
    problemTotalMismatch: "Divergência no total",
    problemCategoryMismatch: "Divergência de categoria",
    problemLowOcr: "Baixa confiança do OCR",
    problemDuplicate: "Possível duplicidade",
    problemPolicyEvidence: "Evidência de política necessária",
    problemMissingDate: "Data da nota ausente",
    problemMissingMerchant: "Estabelecimento ausente",
    problemInvalidTaxId: "Documento fiscal inválido",
    claimedAmountRange: "Valor declarado",
    minimum: "Mínimo",
    maximum: "Máximo",
    submittedRange: "Data de envio",
    from: "De",
    to: "Até",
    pendingAge: "Tempo pendente",
    anyAge: "Qualquer período",
    ageUnder4h: "Menos de 4 horas",
    age4to24h: "De 4 a 24 horas",
    ageOver24h: "Mais de 24 horas",
    resetAll: "Limpar tudo",
    applyFilters: "Aplicar filtros",
    activeFilters: "Filtros ativos",
    clearAll: "Limpar todos",
    loadingQueue: "Carregando fila de revisão…",
    loadingQueueHint: "Filtros complexos podem levar alguns instantes.",
    queueErrorTitle: "Não foi possível carregar a fila",
    queueErrorMessage: "Verifique sua conexão e tente novamente.",
    queueInvalidQuery: "Um ou mais filtros são inválidos. Revise os valores e tente novamente.",
    sessionExpired: "Sua sessão não é mais válida. Entre novamente e tente outra vez.",
    accessDenied: "Você não tem permissão para acessar esta fila de revisão.",
    serviceUnavailable: "O serviço de revisão está temporariamente indisponível. Tente novamente em breve.",
    tryAgain: "Tentar novamente",
    queueClearTitle: "A fila está vazia",
    queueClearMessage: "Não há reembolsos aguardando revisão.",
    noMatchesTitle: "Nenhum caso corresponde aos filtros",
    noMatchesMessage: "Ajuste ou limpe os filtros atuais para ampliar o resultado.",
    resetFilters: "Limpar filtros",
    queueTableCaption: "Reembolsos pendentes correspondentes à consulta atual",
    request: "Solicitação",
    submitter: "Solicitante",
    merchant: "Estabelecimento",
    claimed: "Declarado",
    primaryProblem: "Problema principal",
    submitted: "Enviado",
    pendingSince: "Pendente desde",
    extractedValue: "Extraído: {amount}",
    status: "Status",
    actions: "Ações",
    openCase: "Abrir caso {id}",
    previous: "Anterior",
    next: "Próxima",
    page: "Página {number}",
    pageSummary: "{count} casos nesta página",
    pageSummaryOne: "1 caso nesta página",
    reimbursement: "Reembolso",
    reviewEvidence: "Revisar evidências",
    closeDetails: "Fechar detalhes do caso",
    close: "Fechar",
    loadingDetails: "Carregando evidências do caso…",
    detailErrorTitle: "Não foi possível carregar os detalhes",
    detailErrorMessage: "Tente abrir o caso novamente.",
    caseNotFound: "Este caso não está mais disponível na fila de revisão.",
    caseSections: "Seções do caso",
    comparison: "Comparação",
    problems: "Problemas",
    evidence: "Evidências",
    rules: "Regras",
    businessTimeline: "Linha do tempo de negócio",
    businessTimelineEyebrow: "Histórico de negócio imutável",
    businessTimelineHelp: "Os eventos de negócio são exibidos separadamente do rastreamento técnico protegido.",
    loadingTimeline: "Carregando linha do tempo de negócio…",
    timelineErrorTitle: "Não foi possível carregar a linha do tempo de negócio",
    timelineErrorMessage: "Tente carregar os eventos de negócio novamente.",
    retryTimeline: "Tentar linha do tempo novamente",
    timelineEmptyTitle: "Nenhum evento de negócio registrado",
    timelineEmptyMessage: "Este caso não possui eventos disponíveis para este revisor.",
    loadMoreEvents: "Carregar mais eventos",
    loadingMoreEvents: "Carregando eventos…",
    timelineLoaded: "{count} eventos de negócio carregados.",
    timelineLoadedOne: "1 evento de negócio carregado.",
    timelineEventEnqueued: "Encaminhado para revisão humana",
    timelineEventDecided: "Decisão humana registrada",
    timelineEventGeneric: "Evento de negócio",
    eventTypeCode: "Tipo do evento",
    eventIdentifier: "ID do evento",
    eventActor: "Ator",
    eventCorrelation: "ID de correlação",
    eventStateChange: "Transição de estado",
    eventOutcome: "Resultado",
    eventReasonOriginal: "Justificativa original",
    eventRequestVersion: "Versão da solicitação",
    eventPolicyVersion: "Versão da política",
    eventRoute: "Roteamento automático",
    eventDecisionId: "ID da decisão",
    eventAutomatedDecisionId: "ID da decisão automática",
    eventExtractionStatus: "Status da extração",
    eventAttachmentCount: "Quantidade de anexos",
    noTimelineDetails: "Nenhum detalhe adicional de negócio foi registrado.",
    decision: "Decisão",
    claimSummary: "Resumo da solicitação",
    submittedBy: "Enviado por",
    policyVersion: "Versão da política",
    attachmentCount: "Anexos",
    decisionSnapshot: "Resumo para decisão",
    claimedExtractedComparison: "Declarado vs. extraído",
    comparisonHint: "Os indicadores auxiliam a revisão; a política continua sendo a autoridade.",
    field: "Campo",
    extracted: "Extraído",
    match: "Compatível",
    mismatch: "Divergente",
    incomplete: "Incompleto",
    whyReview: "Por que é necessário julgamento humano",
    detectedProblems: "Problemas detectados",
    sourceEvidence: "Evidência de origem",
    ocrOutput: "Saída do OCR",
    originalLanguage: "Idioma original",
    normalizedObject: "Objeto normalizado",
    extractedReceipt: "Nota extraída",
    deterministicPolicy: "Política determinística",
    ruleEvaluations: "Avaliações das regras",
    rule: "Regra",
    version: "Versão",
    result: "Resultado",
    explanation: "Explicação",
    originalFiles: "Arquivos originais",
    attachments: "Anexos",
    attachmentLimitation: "Este assessment registra apenas as referências dos arquivos. A visualização e o download autorizados ainda não foram implementados.",
    authoritativeAction: "Ação humana autoritativa",
    recordDecision: "Registrar sua decisão",
    decisionAuditNotice: "Sua identidade autenticada, justificativa, horário e versão do caso serão gravados na trilha de auditoria imutável.",
    mandatoryRejectionNotice: "Uma regra de rejeição obrigatória se aplica. Este caso de alto valor ainda exige revisão humana, mas não pode ser aprovado.",
    rationale: "Justificativa",
    required: "obrigatória",
    rationalePlaceholder: "Explique as evidências e o raciocínio que sustentam sua decisão.",
    rationaleHint: "Não inclua senhas, tokens ou dados pessoais sem relação com o caso.",
    rejectReimbursement: "Rejeitar reembolso",
    approveReimbursement: "Aprovar reembolso",
    finalConfirmation: "Confirmação final",
    confirmDecision: "Confirmar decisão",
    immutableWarning: "Esta decisão não poderá ser editada depois de registrada.",
    goBack: "Voltar",
    confirmAndRecord: "Confirmar e registrar",
    confirmApprove: "Confirmar aprovação",
    confirmReject: "Confirmar rejeição",
    confirmApproveCopy: "Você está prestes a aprovar {id}. Isso criará um registro de auditoria imutável.",
    confirmRejectCopy: "Você está prestes a rejeitar {id}. Isso criará um registro de auditoria imutável.",
    rationaleRequired: "É obrigatório informar uma justificativa antes de registrar a decisão.",
    decisionRecorded: "Decisão registrada. Evento de auditoria {eventId}.",
    caseChanged: "Este caso mudou antes do registro da sua decisão. O estado mais recente foi carregado.",
    decisionFailed: "Não foi possível registrar a decisão. Revise o caso e tente novamente.",
    receiptDate: "Data da nota",
    extractedTotal: "Total extraído",
    merchantName: "Estabelecimento",
    taxId: "Documento fiscal",
    warnings: "Alertas",
    evidenceItems: "Evidências",
    noExplicitProblem: "Nenhum problema explícito",
    noAdditionalProblem: "Nenhum problema adicional foi registrado.",
    noRules: "Nenhuma avaliação de regra foi registrada.",
    noAttachments: "Nenhuma referência de anexo foi registrada.",
    noOcr: "Nenhum texto de OCR foi registrado.",
    notAvailable: "Não disponível",
    none: "Nenhum",
    pendingReview: "Revisão pendente",
    approvedAfterReview: "Aprovado após revisão",
    rejectedAfterReview: "Rejeitado após revisão",
    approved: "Aprovado",
    rejected: "Rejeitado",
    passed: "Aprovado",
    needsReview: "Revisar",
    ruleRejected: "Rejeitado",
    submittedAt: "Enviado em {date}",
    lastUpdated: "Atualizado em {date}",
    problemsCount: "{count} problemas",
    oneProblem: "1 problema",
    noPrimaryProblem: "Nenhum problema principal",
    queueLoaded: "Fila carregada com {count} casos nesta página.",
    queueLoadedOne: "Fila carregada com 1 caso nesta página.",
    tableViewActive: "Visualização em tabela ativada.",
    cardViewActive: "Visualização em cards ativada.",
    filterSearch: "Busca",
    filterCategory: "Categoria",
    filterProblem: "Problema",
    filterMinimum: "Mínimo",
    filterMaximum: "Máximo",
    filterSubmittedFrom: "Enviado a partir de",
    filterSubmittedTo: "Enviado até",
    filterAge: "Tempo pendente",
    removeFilter: "Remover filtro {filter}",
    invalidAmountRange: "O valor máximo deve ser maior ou igual ao valor mínimo.",
    invalidDateRange: "A data final deve ser igual ou posterior à data inicial.",
    invalidAmount: "Use um valor não negativo com no máximo duas casas decimais.",
  },
  es: {
    documentTitle: "Expense Agent · Operaciones de revisión",
    skipToWorklist: "Ir a la lista de revisión",
    brandSubtitle: "Área de revisión humana",
    workspaceLabel: "Área actual",
    reviewQueueNav: "Cola de revisión",
    language: "Idioma",
    authenticatedReviewer: "Revisor autenticado",
    signedInAs: "Sesión iniciada como",
    loadingIdentity: "Cargando identidad…",
    operationsEyebrow: "Operaciones financieras",
    pageTitle: "Operaciones de revisión",
    pageDescription: "Encuentra rápidamente el caso correcto, compara la evidencia y registra una decisión responsable.",
    refresh: "Actualizar",
    queueOverview: "Resumen de la cola",
    totalPending: "Total pendiente",
    allPendingCases: "Todos los casos pendientes",
    currentPageOnly: "Solo la página actual",
    urgentPending: "Esperando más de 24h",
    oldestFirstHint: "Prioriza los casos más antiguos",
    highValue: "Alto valor",
    configuredThreshold: "Umbral configurado",
    highValueAbove: "Superior a {amount}",
    amountMismatch: "Diferencia de importe",
    claimedVsExtracted: "Declarado frente a extraído",
    worklistEyebrow: "Lista operativa",
    pendingCases: "Casos pendientes",
    view: "Vista",
    tableView: "Tabla",
    cardView: "Tarjetas",
    searchLabel: "Buscar casos pendientes",
    searchPlaceholder: "ID de solicitud, solicitante o comercio",
    filters: "Filtros",
    sortBy: "Ordenar por",
    sortOldest: "Mayor tiempo de espera",
    sortNewest: "Pendiente recientemente",
    sortAmountDesc: "Mayor importe",
    sortAmountAsc: "Menor importe",
    sortSubmittedNewest: "Enviado recientemente",
    rows: "Filas",
    category: "Categoría",
    allCategoriesOrCode: "Todas las categorías o código exacto",
    categoryClientMeal: "Comida con cliente",
    categoryMeals: "Comidas",
    categoryLodging: "Alojamiento",
    categoryTransport: "Transporte",
    categoryOfficeSupplies: "Material de oficina",
    categoryOther: "Otros",
    problemType: "Tipo de problema",
    allProblemsOrCode: "Todos los problemas o código exacto",
    allProblems: "Todos los problemas",
    problemAmountMismatch: "Diferencia de importe",
    problemTotalMismatch: "Diferencia en el total",
    problemCategoryMismatch: "Diferencia de categoría",
    problemLowOcr: "Baja confianza del OCR",
    problemDuplicate: "Posible duplicado",
    problemPolicyEvidence: "Se requiere evidencia de política",
    problemMissingDate: "Falta la fecha del recibo",
    problemMissingMerchant: "Falta el comercio",
    problemInvalidTaxId: "Identificación fiscal inválida",
    claimedAmountRange: "Importe declarado",
    minimum: "Mínimo",
    maximum: "Máximo",
    submittedRange: "Fecha de envío",
    from: "Desde",
    to: "Hasta",
    pendingAge: "Tiempo pendiente",
    anyAge: "Cualquier período",
    ageUnder4h: "Menos de 4 horas",
    age4to24h: "De 4 a 24 horas",
    ageOver24h: "Más de 24 horas",
    resetAll: "Restablecer todo",
    applyFilters: "Aplicar filtros",
    activeFilters: "Filtros activos",
    clearAll: "Limpiar todos",
    loadingQueue: "Cargando cola de revisión…",
    loadingQueueHint: "Los filtros complejos pueden tardar unos instantes.",
    queueErrorTitle: "No se pudo cargar la cola",
    queueErrorMessage: "Comprueba tu conexión e inténtalo de nuevo.",
    queueInvalidQuery: "Uno o más filtros no son válidos. Revisa los valores e inténtalo de nuevo.",
    sessionExpired: "Tu sesión ya no es válida. Inicia sesión de nuevo y vuelve a intentarlo.",
    accessDenied: "No tienes permiso para acceder a esta cola de revisión.",
    serviceUnavailable: "El servicio de revisión no está disponible temporalmente. Inténtalo de nuevo en breve.",
    tryAgain: "Intentar de nuevo",
    queueClearTitle: "La cola está vacía",
    queueClearMessage: "No hay reembolsos esperando revisión.",
    noMatchesTitle: "Ningún caso coincide con los filtros",
    noMatchesMessage: "Ajusta o limpia los filtros actuales para ampliar el resultado.",
    resetFilters: "Limpiar filtros",
    queueTableCaption: "Reembolsos pendientes que coinciden con la consulta actual",
    request: "Solicitud",
    submitter: "Solicitante",
    merchant: "Comercio",
    claimed: "Declarado",
    primaryProblem: "Problema principal",
    submitted: "Enviado",
    pendingSince: "Pendiente desde",
    extractedValue: "Extraído: {amount}",
    status: "Estado",
    actions: "Acciones",
    openCase: "Abrir caso {id}",
    previous: "Anterior",
    next: "Siguiente",
    page: "Página {number}",
    pageSummary: "{count} casos en esta página",
    pageSummaryOne: "1 caso en esta página",
    reimbursement: "Reembolso",
    reviewEvidence: "Revisar evidencia",
    closeDetails: "Cerrar detalles del caso",
    close: "Cerrar",
    loadingDetails: "Cargando evidencia del caso…",
    detailErrorTitle: "No se pudieron cargar los detalles",
    detailErrorMessage: "Intenta abrir el caso de nuevo.",
    caseNotFound: "Este caso ya no está disponible en la cola de revisión.",
    caseSections: "Secciones del caso",
    comparison: "Comparación",
    problems: "Problemas",
    evidence: "Evidencia",
    rules: "Reglas",
    businessTimeline: "Cronología del negocio",
    businessTimelineEyebrow: "Historial de negocio inmutable",
    businessTimelineHelp: "Los eventos de negocio se muestran separados de la traza técnica protegida.",
    loadingTimeline: "Cargando la cronología del negocio…",
    timelineErrorTitle: "No se pudo cargar la cronología del negocio",
    timelineErrorMessage: "Intenta cargar de nuevo los eventos de negocio.",
    retryTimeline: "Reintentar cronología",
    timelineEmptyTitle: "No hay eventos de negocio registrados",
    timelineEmptyMessage: "Este caso no tiene eventos disponibles para este revisor.",
    loadMoreEvents: "Cargar más eventos",
    loadingMoreEvents: "Cargando eventos…",
    timelineLoaded: "Se cargaron {count} eventos de negocio.",
    timelineLoadedOne: "Se cargó 1 evento de negocio.",
    timelineEventEnqueued: "Enviado a revisión humana",
    timelineEventDecided: "Decisión humana registrada",
    timelineEventGeneric: "Evento de negocio",
    eventTypeCode: "Tipo de evento",
    eventIdentifier: "ID del evento",
    eventActor: "Actor",
    eventCorrelation: "ID de correlación",
    eventStateChange: "Transición de estado",
    eventOutcome: "Resultado",
    eventReasonOriginal: "Justificación original",
    eventRequestVersion: "Versión de la solicitud",
    eventPolicyVersion: "Versión de la política",
    eventRoute: "Ruta automática",
    eventDecisionId: "ID de decisión",
    eventAutomatedDecisionId: "ID de decisión automática",
    eventExtractionStatus: "Estado de extracción",
    eventAttachmentCount: "Cantidad de adjuntos",
    noTimelineDetails: "No se registraron detalles adicionales de negocio.",
    decision: "Decisión",
    claimSummary: "Resumen de la solicitud",
    submittedBy: "Enviado por",
    policyVersion: "Versión de la política",
    attachmentCount: "Adjuntos",
    decisionSnapshot: "Resumen para decisión",
    claimedExtractedComparison: "Declarado vs. extraído",
    comparisonHint: "Los indicadores ayudan a revisar; la política sigue siendo la autoridad.",
    field: "Campo",
    extracted: "Extraído",
    match: "Coincide",
    mismatch: "Diferente",
    incomplete: "Incompleto",
    whyReview: "Por qué se necesita juicio humano",
    detectedProblems: "Problemas detectados",
    sourceEvidence: "Evidencia de origen",
    ocrOutput: "Salida del OCR",
    originalLanguage: "Idioma original",
    normalizedObject: "Objeto normalizado",
    extractedReceipt: "Recibo extraído",
    deterministicPolicy: "Política determinista",
    ruleEvaluations: "Evaluaciones de reglas",
    rule: "Regla",
    version: "Versión",
    result: "Resultado",
    explanation: "Explicación",
    originalFiles: "Archivos originales",
    attachments: "Adjuntos",
    attachmentLimitation: "Esta evaluación solo registra las referencias de los archivos. La vista previa y la descarga autorizadas aún no están implementadas.",
    authoritativeAction: "Acción humana autoritativa",
    recordDecision: "Registrar tu decisión",
    decisionAuditNotice: "Tu identidad autenticada, justificación, hora y versión del caso se guardarán en el registro de auditoría inmutable.",
    mandatoryRejectionNotice: "Se aplica una regla de rechazo obligatorio. Este caso de alto valor aún requiere revisión humana, pero no puede aprobarse.",
    rationale: "Justificación",
    required: "obligatoria",
    rationalePlaceholder: "Explica la evidencia y el razonamiento que sustentan tu decisión.",
    rationaleHint: "No incluyas contraseñas, tokens ni datos personales ajenos al caso.",
    rejectReimbursement: "Rechazar reembolso",
    approveReimbursement: "Aprobar reembolso",
    finalConfirmation: "Confirmación final",
    confirmDecision: "Confirmar decisión",
    immutableWarning: "Esta decisión no se podrá editar después de registrarla.",
    goBack: "Volver",
    confirmAndRecord: "Confirmar y registrar",
    confirmApprove: "Confirmar aprobación",
    confirmReject: "Confirmar rechazo",
    confirmApproveCopy: "Vas a aprobar {id}. Esto creará un registro de auditoría inmutable.",
    confirmRejectCopy: "Vas a rechazar {id}. Esto creará un registro de auditoría inmutable.",
    rationaleRequired: "Debes indicar una justificación antes de registrar la decisión.",
    decisionRecorded: "Decisión registrada. Evento de auditoría {eventId}.",
    caseChanged: "Este caso cambió antes de registrar tu decisión. Se cargó el estado más reciente.",
    decisionFailed: "No se pudo registrar la decisión. Revisa el caso e inténtalo de nuevo.",
    receiptDate: "Fecha del recibo",
    extractedTotal: "Total extraído",
    merchantName: "Comercio",
    taxId: "Identificación fiscal",
    warnings: "Alertas",
    evidenceItems: "Evidencia",
    noExplicitProblem: "Ningún problema explícito",
    noAdditionalProblem: "No se registró ningún problema adicional.",
    noRules: "No se registró ninguna evaluación de reglas.",
    noAttachments: "No se registró ninguna referencia de adjunto.",
    noOcr: "No se registró ningún texto de OCR.",
    notAvailable: "No disponible",
    none: "Ninguno",
    pendingReview: "Revisión pendiente",
    approvedAfterReview: "Aprobado tras revisión",
    rejectedAfterReview: "Rechazado tras revisión",
    approved: "Aprobado",
    rejected: "Rechazado",
    passed: "Aprobado",
    needsReview: "Revisar",
    ruleRejected: "Rechazado",
    submittedAt: "Enviado el {date}",
    lastUpdated: "Actualizado el {date}",
    problemsCount: "{count} problemas",
    oneProblem: "1 problema",
    noPrimaryProblem: "Ningún problema principal",
    queueLoaded: "Cola cargada con {count} casos en esta página.",
    queueLoadedOne: "Cola cargada con 1 caso en esta página.",
    tableViewActive: "Vista de tabla activada.",
    cardViewActive: "Vista de tarjetas activada.",
    filterSearch: "Búsqueda",
    filterCategory: "Categoría",
    filterProblem: "Problema",
    filterMinimum: "Mínimo",
    filterMaximum: "Máximo",
    filterSubmittedFrom: "Enviado desde",
    filterSubmittedTo: "Enviado hasta",
    filterAge: "Tiempo pendiente",
    removeFilter: "Quitar filtro {filter}",
    invalidAmountRange: "El importe máximo debe ser mayor o igual que el mínimo.",
    invalidDateRange: "La fecha final debe ser igual o posterior a la fecha inicial.",
    invalidAmount: "Usa un importe no negativo con un máximo de dos decimales.",
  },
};

const statusTranslationKeys = {
  pending_review: "pendingReview",
  approved_after_review: "approvedAfterReview",
  rejected_after_review: "rejectedAfterReview",
  approved: "approved",
  rejected: "rejected",
};

const ruleOutcomeTranslationKeys = {
  pass: "passed",
  review: "needsReview",
  reject: "ruleRejected",
  approved: "approved",
  rejected: "rejected",
};

const problemTranslationKeys = {
  AMOUNT_MISMATCH: "problemAmountMismatch",
  TOTAL_MISMATCH: "problemTotalMismatch",
  CATEGORY_MISMATCH: "problemCategoryMismatch",
  LOW_OCR_CONFIDENCE: "problemLowOcr",
  DUPLICATE_RECEIPT: "problemDuplicate",
  POLICY_LIMIT_EVIDENCE: "problemPolicyEvidence",
  MISSING_RECEIPT_DATE: "problemMissingDate",
  MISSING_MERCHANT: "problemMissingMerchant",
  TAX_ID_INVALID: "problemInvalidTaxId",
  NO_EXPLICIT_PROBLEM: "noExplicitProblem",
};

const categoryTranslationKeys = {
  client_meal: "categoryClientMeal",
  meals: "categoryMeals",
  lodging: "categoryLodging",
  transport: "categoryTransport",
  office_supplies: "categoryOfficeSupplies",
  other: "categoryOther",
};

const ageTranslationKeys = {
  under_4h: "ageUnder4h",
  "4h_to_24h": "age4to24h",
  over_24h: "ageOver24h",
};

const businessEventTranslationKeys = {
  review_case_enqueued: "timelineEventEnqueued",
  human_review_decided: "timelineEventDecided",
};

const businessPayloadFields = Object.freeze([
  "from_status",
  "to_status",
  "outcome",
  "reason",
  "request_version",
  "policy_version",
  "route",
  "decision_id",
  "automated_decision_id",
  "extraction_status",
  "attachment_count",
]);

const filterDefinitions = {
  search: { label: "filterSearch" },
  category: { label: "filterCategory" },
  problemCode: { label: "filterProblem" },
  minAmount: { label: "filterMinimum" },
  maxAmount: { label: "filterMaximum" },
  submittedFrom: { label: "filterSubmittedFrom", format: "date" },
  submittedTo: { label: "filterSubmittedTo", format: "date" },
  ageBucket: { label: "filterAge", format: "age" },
};

const elementIds = [
  "language-select", "reviewer-name", "last-updated", "refresh-queue", "worklist",
  "metric-total", "metric-total-note", "metric-urgent", "metric-high-value",
  "metric-high-value-note", "metric-mismatch", "table-view-button", "card-view-button",
  "filter-form", "search-input", "filter-toggle", "filter-count", "sort-select",
  "page-size-select", "filter-panel", "category-filter", "problem-filter",
  "min-amount-filter", "max-amount-filter", "submitted-from-filter",
  "submitted-to-filter", "age-filter", "filter-validation", "reset-filters",
  "active-filters", "filter-chips", "clear-active-filters", "queue-loading",
  "queue-error", "queue-error-message", "retry-queue", "queue-empty",
  "queue-empty-title", "queue-empty-message", "empty-reset-filters", "queue-results",
  "table-view", "queue-table-body", "card-view", "page-summary", "previous-page",
  "next-page", "page-number", "case-dialog", "request-id", "case-submitted",
  "case-status", "close-case", "detail-loading", "detail-error", "detail-error-message",
  "retry-detail", "case-content", "submitted-by", "policy-version",
  "attachment-count-summary", "case-pending-since", "comparison-body", "problem-count", "problem-list",
  "ocr-text", "facts-list", "rules-body", "attachment-count", "attachment-list",
  "timeline-section", "timeline-count", "timeline-loading", "timeline-error",
  "timeline-error-message", "retry-timeline", "timeline-empty", "timeline-content",
  "timeline-list", "timeline-load-more",
  "decision-panel", "mandatory-rejection-notice", "decision-reason", "reason-counter", "reject-button",
  "approve-button", "confirm-dialog", "confirm-title", "confirm-copy", "confirm-icon",
  "confirm-button", "toast", "announcer",
];

const elements = Object.fromEntries(elementIds.map((id) => [id, document.getElementById(id)]));

function detectLanguage() {
  const preferences = Array.isArray(navigator.languages) && navigator.languages.length
    ? navigator.languages
    : [navigator.language];
  for (const preference of preferences) {
    const normalized = String(preference ?? "").toLowerCase();
    if (normalized.startsWith("pt")) return "pt-BR";
    if (normalized.startsWith("es")) return "es";
    if (normalized.startsWith("en")) return "en";
  }
  return "en";
}

const state = {
  language: detectLanguage(),
  csrfToken: null,
  reviewerName: null,
  filters: {
    search: "",
    category: "",
    problemCode: "",
    minAmount: "",
    maxAmount: "",
    submittedFrom: "",
    submittedTo: "",
    ageBucket: "",
    sort: "pending_oldest",
    limit: 25,
  },
  cursor: null,
  cursorHistory: [],
  pageNumber: 1,
  page: { limit: 25, sort: "pending_oldest", has_more: false, next_cursor: null },
  summary: null,
  queueItems: [],
  queueController: null,
  selectedRequestId: null,
  selectedEtag: null,
  selectedCase: null,
  timelineItems: [],
  timelinePage: { limit: 25, has_more: false, next_cursor: null },
  timelineMode: "idle",
  timelineErrorKey: null,
  timelineController: null,
  timelineLoadingMore: false,
  lastCaseTrigger: null,
  pendingOutcome: null,
  deciding: false,
  view: window.matchMedia("(max-width: 760px)").matches ? "cards" : "table",
  queueMode: "loading",
};

let searchTimer = null;
let toastTimer = null;

function t(key, variables = {}) {
  const catalog = translations[state.language] ?? translations.en;
  const template = catalog[key] ?? translations.en[key] ?? key;
  return template.replace(/\{([a-zA-Z0-9_]+)\}/g, (_match, name) => String(variables[name] ?? ""));
}

function applyTranslations() {
  document.documentElement.lang = state.language;
  document.title = t("documentTitle");
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => {
    node.setAttribute("aria-label", t(node.dataset.i18nAriaLabel));
  });
  document.querySelectorAll("[data-i18n-title]").forEach((node) => {
    node.setAttribute("title", t(node.dataset.i18nTitle));
  });
  document.querySelectorAll("[data-i18n-label]").forEach((node) => {
    node.setAttribute("label", t(node.dataset.i18nLabel));
  });
  elements["language-select"].value = state.language;
  elements["reviewer-name"].textContent = state.reviewerName ?? t("loadingIdentity");
}

function textElement(tag, value, className = null) {
  const node = document.createElement(tag);
  if (value !== null && value !== undefined) node.textContent = value;
  if (className) node.className = className;
  return node;
}

function displayValue(value) {
  if (value === null || value === undefined || value === "") return t("notAvailable");
  if (Array.isArray(value)) return value.length ? value.map((item) => displayOriginalValue(item)).join(", ") : t("none");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function displayOriginalValue(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function formatMoney(money) {
  if (!money || money.amount === null || money.amount === undefined) return "—";
  const amount = Number(money.amount);
  if (!Number.isFinite(amount)) return `${money.currency ?? ""} ${money.amount}`.trim();
  try {
    return new Intl.NumberFormat(state.language, {
      style: "currency",
      currency: money.currency ?? "BRL",
    }).format(amount);
  } catch (_error) {
    return `${money.currency ?? ""} ${money.amount}`.trim();
  }
}

function formatDate(value, includeTime = true) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const options = includeTime
    ? { dateStyle: "medium", timeStyle: "short" }
    : { dateStyle: "medium" };
  return new Intl.DateTimeFormat(state.language, options).format(date);
}

function formatFilterDate(value) {
  if (!value) return "";
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? value : formatDate(date, false);
}

function formatRelativeAge(value) {
  const submitted = new Date(value);
  if (Number.isNaN(submitted.getTime())) return formatDate(value);
  const elapsedMs = Date.now() - submitted.getTime();
  const relative = new Intl.RelativeTimeFormat(state.language, { numeric: "auto" });
  if (elapsedMs < 60 * 60 * 1000) {
    return relative.format(-Math.max(1, Math.round(elapsedMs / 60000)), "minute");
  }
  if (elapsedMs < 48 * 60 * 60 * 1000) {
    return relative.format(-Math.max(1, Math.round(elapsedMs / 3600000)), "hour");
  }
  return relative.format(-Math.max(1, Math.round(elapsedMs / 86400000)), "day");
}

function translatedCategory(code, includeCode = false) {
  if (!code) return t("notAvailable");
  const key = categoryTranslationKeys[String(code).toLowerCase()];
  if (!key) return String(code);
  const label = t(key);
  return includeCode ? `${label} · ${code}` : label;
}

function translatedProblem(code) {
  if (!code) return t("noPrimaryProblem");
  const key = problemTranslationKeys[String(code).toUpperCase()];
  return key ? t(key) : String(code).replaceAll("_", " ");
}

function translatedStatus(status) {
  const key = statusTranslationKeys[status];
  return key ? t(key) : String(status ?? t("notAvailable")).replaceAll("_", " ");
}

function translatedOutcome(outcome) {
  const key = ruleOutcomeTranslationKeys[outcome];
  return key ? t(key) : String(outcome ?? t("notAvailable")).replaceAll("_", " ");
}

function showToast(message, isError = false) {
  window.clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.toggle("error", isError);
  elements.toast.hidden = false;
  toastTimer = window.setTimeout(() => {
    elements.toast.hidden = true;
  }, 5500);
}

function announce(message) {
  elements.announcer.textContent = "";
  window.setTimeout(() => {
    elements.announcer.textContent = message;
  }, 20);
}

class ApiError extends Error {
  constructor(status) {
    super(`HTTP ${status}`);
    this.status = status;
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
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

function localizedApiError(error, context) {
  if (error?.status === 401) return t("sessionExpired");
  if (error?.status === 403) return t("accessDenied");
  if (error?.status === 404 && context === "detail") return t("caseNotFound");
  if (error?.status === 422 && context === "queue") return t("queueInvalidQuery");
  if (error?.status === 429 || error?.status >= 500) return t("serviceUnavailable");
  return context === "detail" ? t("detailErrorMessage") : t("queueErrorMessage");
}

async function loadSession() {
  const { body } = await api("/api/session");
  state.csrfToken = body?.csrf_token ?? null;
  state.reviewerName = body?.reviewer?.display_name ?? t("notAvailable");
  elements["reviewer-name"].textContent = state.reviewerName;
}

function setQueueState(mode, errorMessage = null) {
  state.queueMode = mode;
  elements["queue-loading"].hidden = mode !== "loading";
  elements["queue-error"].hidden = mode !== "error";
  elements["queue-empty"].hidden = mode !== "empty";
  elements["queue-results"].hidden = mode !== "results";
  elements.worklist.setAttribute("aria-busy", String(mode === "loading"));
  if (errorMessage) elements["queue-error-message"].textContent = errorMessage;
}

function queueProblem(item) {
  if (item?.primary_problem) return item.primary_problem;
  if (Array.isArray(item?.problems) && item.problems.length) return item.problems[0];
  if (Array.isArray(item?.problem_codes) && item.problem_codes.length) {
    return { code: item.problem_codes[0], message: null };
  }
  if (item?.problem_code) return { code: item.problem_code, message: null };
  return null;
}

function problemCount(item) {
  if (Array.isArray(item?.problem_codes)) return item.problem_codes.length;
  if (Array.isArray(item?.problems)) return item.problems.length;
  return queueProblem(item) ? 1 : 0;
}

function queueMerchant(item) {
  return item?.merchant_name ?? item?.extraction?.facts?.merchant_name ?? null;
}

function createRequestButton(item, className = "request-link") {
  const button = textElement("button", item.request_id, className);
  button.type = "button";
  button.setAttribute("aria-label", t("openCase", { id: item.request_id }));
  button.addEventListener("click", (event) => loadCase(item.request_id, event.currentTarget));
  return button;
}

function renderTable(items) {
  elements["queue-table-body"].replaceChildren();
  for (const item of items) {
    const row = document.createElement("tr");
    if (item.request_id === state.selectedRequestId) row.classList.add("is-selected");

    const requestCell = document.createElement("td");
    requestCell.append(createRequestButton(item));

    const submitterCell = textElement("td", item.submitted_by ?? t("notAvailable"), "submitter-cell");
    submitterCell.title = item.submitted_by ?? "";

    const merchant = queueMerchant(item);
    const merchantCell = textElement("td", merchant ?? t("notAvailable"), "merchant-cell");
    merchantCell.title = merchant ?? "";

    const categoryCell = document.createElement("td");
    categoryCell.append(textElement("span", translatedCategory(item.claimed_category), "category-badge"));

    const amountCell = document.createElement("td");
    amountCell.className = "numeric";
    const amountContent = textElement("div", null, "primary-cell amount-cell-content");
    amountContent.append(textElement("strong", formatMoney(item.claimed_amount)));
    if (item.extracted_amount) {
      amountContent.append(textElement("small", t("extractedValue", { amount: formatMoney(item.extracted_amount) })));
      if (compareValues(item.claimed_amount, item.extracted_amount, "money") === "mismatch") {
        amountContent.classList.add("amount-difference");
      }
    }
    amountCell.append(amountContent);
    const problem = queueProblem(item);
    const problemCell = document.createElement("td");
    const problemContent = textElement("div", null, "problem-cell");
    const count = problemCount(item);
    problemContent.append(textElement("strong", problem ? translatedProblem(problem.code) : t("noPrimaryProblem")));
    if (count > 1) problemContent.append(textElement("small", t("problemsCount", { count })));
    problemCell.append(problemContent);

    const submittedCell = document.createElement("td");
    const submittedContent = textElement("div", null, "primary-cell");
    const pendingSince = item.pending_since ?? item.submitted_at;
    submittedContent.append(
      textElement("strong", formatRelativeAge(pendingSince)),
      textElement("small", formatDate(pendingSince)),
    );
    submittedCell.append(submittedContent);

    const statusCell = document.createElement("td");
    statusCell.append(textElement("span", translatedStatus(item.status ?? "pending_review"), "status-pill"));

    const actionCell = document.createElement("td");
    const action = textElement("button", "→", "open-case-button");
    action.type = "button";
    action.setAttribute("aria-label", t("openCase", { id: item.request_id }));
    action.addEventListener("click", (event) => loadCase(item.request_id, event.currentTarget));
    actionCell.append(action);

    row.append(requestCell, submitterCell, merchantCell, categoryCell, amountCell, problemCell, submittedCell, statusCell, actionCell);
    elements["queue-table-body"].append(row);
  }
}

function renderCards(items) {
  elements["card-view"].replaceChildren();
  for (const item of items) {
    const listItem = document.createElement("li");
    const card = textElement("article", null, "case-card");
    if (item.request_id === state.selectedRequestId) card.classList.add("is-selected");

    const header = textElement("div", null, "case-card-header");
    header.append(createRequestButton(item), textElement("span", translatedStatus(item.status ?? "pending_review"), "status-pill"));

    const submitter = textElement("p", item.submitted_by ?? t("notAvailable"), "case-card-submittee");
    const amountRow = textElement("div", null, "case-card-row");
    amountRow.append(textElement("span", t("claimed")), textElement("strong", formatMoney(item.claimed_amount)));
    const merchantRow = textElement("div", null, "case-card-row");
    merchantRow.append(textElement("span", t("merchant")), textElement("strong", queueMerchant(item) ?? t("notAvailable")));

    const problem = queueProblem(item);
    const problemBox = textElement("div", problem ? translatedProblem(problem.code) : t("noPrimaryProblem"), "case-card-problem");
    if (problem?.message) problemBox.title = problem.message;

    const footer = textElement("div", null, "case-card-footer");
    const pendingSince = item.pending_since ?? item.submitted_at;
    const time = textElement("time", formatRelativeAge(pendingSince));
    time.dateTime = pendingSince ?? "";
    const open = textElement("button", t("reviewEvidence"), "text-button");
    open.type = "button";
    open.setAttribute("aria-label", t("openCase", { id: item.request_id }));
    open.addEventListener("click", (event) => loadCase(item.request_id, event.currentTarget));
    footer.append(time, open);

    card.append(header, submitter, amountRow, merchantRow, problemBox, footer);
    listItem.append(card);
    elements["card-view"].append(listItem);
  }
}

function normalizeQueueResponse(body) {
  const items = Array.isArray(body) ? body : (Array.isArray(body?.items) ? body.items : []);
  const page = body?.page && typeof body.page === "object"
    ? body.page
    : {
        limit: state.filters.limit,
        sort: state.filters.sort,
        has_more: false,
        next_cursor: null,
      };
  return { items, page, summary: body?.summary ?? null };
}

function renderMetrics(summary, items) {
  const hasSummary = summary && typeof summary === "object";
  elements["metric-total"].textContent = String(hasSummary ? (summary.total_pending ?? items.length) : items.length);
  elements["metric-total-note"].textContent = t(hasSummary ? "allPendingCases" : "currentPageOnly");
  elements["metric-urgent"].textContent = hasSummary
    ? String(summary.urgent_pending ?? summary.over_24h ?? "—")
    : "—";
  elements["metric-high-value"].textContent = hasSummary ? String(summary.high_value ?? "—") : "—";
  elements["metric-mismatch"].textContent = hasSummary ? String(summary.amount_mismatch ?? "—") : "—";
  elements["metric-high-value-note"].textContent = summary?.high_value_threshold
    ? t("highValueAbove", { amount: formatMoney(summary.high_value_threshold) })
    : t("configuredThreshold");
  elements["last-updated"].textContent = summary?.as_of
    ? t("lastUpdated", { date: formatDate(summary.as_of) })
    : "";
}

function renderPagination() {
  const count = state.queueItems.length;
  elements["page-summary"].textContent = t(count === 1 ? "pageSummaryOne" : "pageSummary", { count });
  elements["page-number"].textContent = t("page", { number: state.pageNumber });
  elements["previous-page"].disabled = state.cursorHistory.length === 0;
  elements["next-page"].disabled = !state.page?.has_more || !state.page?.next_cursor;
}

function renderQueue() {
  renderTable(state.queueItems);
  renderCards(state.queueItems);
  renderMetrics(state.summary, state.queueItems);
  renderPagination();
  renderActiveFilters();
  updateView();

  if (!state.queueItems.length) {
    const filtered = activeFilterEntries().length > 0;
    elements["queue-empty-title"].textContent = t(filtered ? "noMatchesTitle" : "queueClearTitle");
    elements["queue-empty-message"].textContent = t(filtered ? "noMatchesMessage" : "queueClearMessage");
    elements["empty-reset-filters"].hidden = !filtered;
    setQueueState("empty");
  } else {
    setQueueState("results");
  }
}

function dateBoundary(value, endOfDay = false) {
  if (!value) return null;
  const suffix = endOfDay ? "T23:59:59.999" : "T00:00:00.000";
  const date = new Date(`${value}${suffix}`);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function buildQueueUrl() {
  const params = new URLSearchParams();
  const mapping = [
    ["search", state.filters.search],
    ["category", state.filters.category],
    ["problem_code", state.filters.problemCode],
    ["min_amount", state.filters.minAmount],
    ["max_amount", state.filters.maxAmount],
    ["submitted_from", dateBoundary(state.filters.submittedFrom)],
    ["submitted_to", dateBoundary(state.filters.submittedTo, true)],
    ["age_bucket", state.filters.ageBucket],
    ["sort", state.filters.sort],
    ["limit", state.filters.limit],
    ["cursor", state.cursor],
  ];
  for (const [key, value] of mapping) {
    if (value !== null && value !== undefined && value !== "") params.set(key, String(value));
  }
  return `/api/reviews?${params.toString()}`;
}

async function loadQueue({ announceResult = true } = {}) {
  if (state.queueController) state.queueController.abort();
  const controller = new AbortController();
  state.queueController = controller;
  setQueueState("loading");
  elements["refresh-queue"].disabled = true;
  try {
    const { body } = await api(buildQueueUrl(), { signal: controller.signal });
    if (controller.signal.aborted) return;
    const normalized = normalizeQueueResponse(body);
    state.queueItems = normalized.items;
    state.page = normalized.page;
    state.summary = normalized.summary;
    renderQueue();
    if (announceResult) {
      const key = state.queueItems.length === 1 ? "queueLoadedOne" : "queueLoaded";
      announce(t(key, { count: state.queueItems.length }));
    }
  } catch (error) {
    if (error?.name === "AbortError") return;
    setQueueState("error", localizedApiError(error, "queue"));
  } finally {
    if (state.queueController === controller) {
      state.queueController = null;
      elements["refresh-queue"].disabled = false;
    }
  }
}

function resetPagination() {
  state.cursor = null;
  state.cursorHistory = [];
  state.pageNumber = 1;
}

function syncFilterControls() {
  elements["search-input"].value = state.filters.search;
  elements["category-filter"].value = state.filters.category;
  elements["problem-filter"].value = state.filters.problemCode;
  elements["min-amount-filter"].value = state.filters.minAmount;
  elements["max-amount-filter"].value = state.filters.maxAmount;
  elements["submitted-from-filter"].value = state.filters.submittedFrom;
  elements["submitted-to-filter"].value = state.filters.submittedTo;
  elements["age-filter"].value = state.filters.ageBucket;
  elements["sort-select"].value = state.filters.sort;
  elements["page-size-select"].value = String(state.filters.limit);
}

function readFilterControls() {
  state.filters.search = elements["search-input"].value.trim();
  state.filters.category = elements["category-filter"].value.trim();
  state.filters.problemCode = elements["problem-filter"].value.trim();
  state.filters.minAmount = elements["min-amount-filter"].value.trim();
  state.filters.maxAmount = elements["max-amount-filter"].value.trim();
  state.filters.submittedFrom = elements["submitted-from-filter"].value;
  state.filters.submittedTo = elements["submitted-to-filter"].value;
  state.filters.ageBucket = elements["age-filter"].value;
}

function validateFilters() {
  const decimalPattern = /^\d+(?:\.\d{1,2})?$/;
  for (const value of [elements["min-amount-filter"].value, elements["max-amount-filter"].value]) {
    if (value && (!decimalPattern.test(value) || Number(value) < 0)) return t("invalidAmount");
  }
  const minimum = Number(elements["min-amount-filter"].value);
  const maximum = Number(elements["max-amount-filter"].value);
  if (elements["min-amount-filter"].value && elements["max-amount-filter"].value && maximum < minimum) {
    return t("invalidAmountRange");
  }
  if (elements["submitted-from-filter"].value && elements["submitted-to-filter"].value
      && elements["submitted-to-filter"].value < elements["submitted-from-filter"].value) {
    return t("invalidDateRange");
  }
  return null;
}

function setFilterValidation(message = null) {
  elements["filter-validation"].textContent = message ?? "";
  elements["filter-validation"].hidden = !message;
}

function applyFilters() {
  window.clearTimeout(searchTimer);
  const error = validateFilters();
  if (error) {
    setFilterValidation(error);
    return;
  }
  setFilterValidation();
  readFilterControls();
  resetPagination();
  renderActiveFilters();
  loadQueue();
}

function clearFilters() {
  window.clearTimeout(searchTimer);
  state.filters = {
    ...state.filters,
    search: "",
    category: "",
    problemCode: "",
    minAmount: "",
    maxAmount: "",
    submittedFrom: "",
    submittedTo: "",
    ageBucket: "",
  };
  syncFilterControls();
  setFilterValidation();
  resetPagination();
  renderActiveFilters();
  loadQueue();
}

function activeFilterEntries() {
  return Object.keys(filterDefinitions)
    .filter((key) => state.filters[key] !== "")
    .map((key) => [key, state.filters[key]]);
}

function filterDisplayValue(key, value) {
  const definition = filterDefinitions[key];
  if (definition?.format === "date") return formatFilterDate(value);
  if (definition?.format === "age") return t(ageTranslationKeys[value] ?? "anyAge");
  if (key === "category") return translatedCategory(value, true);
  if (key === "problemCode") return translatedProblem(value);
  if (key === "minAmount" || key === "maxAmount") return formatMoney({ amount: value, currency: "BRL" });
  return value;
}

function renderActiveFilters() {
  const entries = activeFilterEntries();
  elements["filter-chips"].replaceChildren();
  elements["active-filters"].hidden = entries.length === 0;
  elements["filter-count"].hidden = entries.length === 0;
  elements["filter-count"].textContent = String(entries.length);
  for (const [key, value] of entries) {
    const definition = filterDefinitions[key];
    const chip = textElement("span", null, "filter-chip");
    chip.append(textElement("span", `${t(definition.label)}: ${filterDisplayValue(key, value)}`));
    const remove = textElement("button", "×");
    remove.type = "button";
    remove.setAttribute("aria-label", t("removeFilter", { filter: t(definition.label) }));
    remove.addEventListener("click", () => removeFilter(key));
    chip.append(remove);
    elements["filter-chips"].append(chip);
  }
}

function removeFilter(key) {
  if (key === "search") window.clearTimeout(searchTimer);
  state.filters[key] = "";
  syncFilterControls();
  resetPagination();
  renderActiveFilters();
  loadQueue();
}

function updateView(shouldAnnounce = false) {
  const tableActive = state.view === "table";
  elements["table-view"].hidden = !tableActive;
  elements["card-view"].hidden = tableActive;
  elements["table-view-button"].classList.toggle("is-active", tableActive);
  elements["card-view-button"].classList.toggle("is-active", !tableActive);
  elements["table-view-button"].setAttribute("aria-pressed", String(tableActive));
  elements["card-view-button"].setAttribute("aria-pressed", String(!tableActive));
  if (shouldAnnounce) announce(t(tableActive ? "tableViewActive" : "cardViewActive"));
}

function syncBodyDialogState() {
  const anyOpen = elements["case-dialog"].open || elements["confirm-dialog"].open;
  document.body.classList.toggle("has-dialog", anyOpen);
}

function openCaseDialog() {
  if (!elements["case-dialog"].open) elements["case-dialog"].showModal();
  syncBodyDialogState();
}

function setDetailState(mode, errorMessage = null) {
  elements["detail-loading"].hidden = mode !== "loading";
  elements["detail-error"].hidden = mode !== "error";
  elements["case-content"].hidden = mode !== "content";
  if (errorMessage) elements["detail-error-message"].textContent = errorMessage;
}

function canonicalDecimal(value) {
  const stringValue = String(value ?? "").trim();
  if (!/^[-+]?\d+(?:\.\d+)?$/.test(stringValue)) return stringValue;
  const negative = stringValue.startsWith("-");
  const unsigned = stringValue.replace(/^[-+]/, "");
  const [integerPart, fractionPart = ""] = unsigned.split(".");
  const integer = integerPart.replace(/^0+(?=\d)/, "") || "0";
  const fraction = fractionPart.replace(/0+$/, "");
  return `${negative ? "-" : ""}${integer}${fraction ? `.${fraction}` : ""}`;
}

function compareValues(claimed, extracted, type) {
  if (claimed === null || claimed === undefined || claimed === ""
      || extracted === null || extracted === undefined || extracted === "") return "incomplete";
  if (type === "money") {
    const sameCurrency = String(claimed.currency ?? "").toUpperCase() === String(extracted.currency ?? "").toUpperCase();
    return sameCurrency && canonicalDecimal(claimed.amount) === canonicalDecimal(extracted.amount) ? "match" : "mismatch";
  }
  return String(claimed).trim().toLowerCase() === String(extracted).trim().toLowerCase() ? "match" : "mismatch";
}

function comparisonBadge(result) {
  const symbols = { match: "✓", mismatch: "≠", incomplete: "!" };
  const badge = textElement("span", null, `comparison-result ${result}`);
  badge.append(textElement("span", symbols[result]), textElement("span", t(result)));
  return badge;
}

function renderComparison(caseData) {
  elements["comparison-body"].replaceChildren();
  const facts = caseData.extraction?.facts ?? {};
  const rows = [
    {
      label: t("claimedAmountRange"),
      claimed: caseData.claimed_amount,
      extracted: facts.total,
      render: formatMoney,
      type: "money",
    },
    {
      label: t("category"),
      claimed: caseData.claimed_category,
      extracted: facts.category,
      render: (value) => translatedCategory(value, true),
      type: "text",
    },
  ];
  for (const item of rows) {
    const row = document.createElement("tr");
    const result = compareValues(item.claimed, item.extracted, item.type);
    const resultCell = document.createElement("td");
    resultCell.append(comparisonBadge(result));
    row.append(
      textElement("th", item.label),
      textElement("td", item.render(item.claimed)),
      textElement("td", item.render(item.extracted)),
      resultCell,
    );
    row.firstElementChild.scope = "row";
    elements["comparison-body"].append(row);
  }
}

function renderProblems(problems) {
  elements["problem-list"].replaceChildren();
  elements["problem-count"].textContent = String(problems.length);
  const visible = problems.length
    ? problems
    : [{ code: "NO_EXPLICIT_PROBLEM", message: t("noAdditionalProblem") }];
  for (const problem of visible) {
    const item = textElement("li", null, "problem-item");
    item.append(
      textElement("code", problem.code),
      textElement("strong", translatedProblem(problem.code)),
      textElement("p", problem.message ?? t("notAvailable")),
    );
    elements["problem-list"].append(item);
  }
}

function renderFacts(facts) {
  elements["facts-list"].replaceChildren();
  const values = [
    [t("receiptDate"), facts?.receipt_date],
    [t("extractedTotal"), facts?.total ? formatMoney(facts.total) : null],
    [t("category"), facts?.category ? translatedCategory(facts.category, true) : null],
    [t("merchantName"), facts?.merchant_name],
    [t("taxId"), facts?.tax_id],
    [t("warnings"), facts?.warnings],
    [t("evidenceItems"), facts?.evidence],
  ];
  for (const [label, value] of values) {
    elements["facts-list"].append(textElement("dt", label), textElement("dd", displayValue(value)));
  }
}

function renderRules(rules) {
  elements["rules-body"].replaceChildren();
  for (const rule of rules) {
    const row = document.createElement("tr");
    row.append(
      textElement("td", rule.rule_id),
      textElement("td", rule.rule_version),
      textElement("td", translatedOutcome(rule.outcome), `rule-result ${rule.outcome}`),
      textElement("td", rule.message),
    );
    elements["rules-body"].append(row);
  }
  if (!rules.length) {
    const row = document.createElement("tr");
    const cell = textElement("td", t("noRules"));
    cell.colSpan = 4;
    row.append(cell);
    elements["rules-body"].append(row);
  }
}

function primitiveBusinessValue(value) {
  if (value === null || value === undefined || value === "") return null;
  if (!["string", "number", "boolean"].includes(typeof value)) return null;
  return String(value);
}

function allowedBusinessPayload(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return {};
  return Object.fromEntries(
    businessPayloadFields
      .filter((key) => primitiveBusinessValue(payload[key]) !== null)
      .map((key) => [key, payload[key]]),
  );
}

function localizedCode(value, translator) {
  const code = primitiveBusinessValue(value);
  if (code === null) return null;
  return `${translator(code)} · ${code}`;
}

function appendTimelineFact(list, label, value, className = null) {
  const normalized = primitiveBusinessValue(value);
  if (normalized === null) return false;
  const item = textElement("div", null, "business-event-fact");
  item.append(textElement("dt", label), textElement("dd", normalized, className));
  list.append(item);
  return true;
}

function renderBusinessEvent(event) {
  const item = textElement("li", null, "business-event");
  const marker = textElement("span", null, "business-event-marker");
  marker.setAttribute("aria-hidden", "true");
  item.append(marker);

  const card = textElement("article", null, "business-event-card");
  const header = textElement("header", null, "business-event-header");
  const heading = textElement("div", null, "business-event-heading");
  const eventType = primitiveBusinessValue(event?.event_type) ?? t("notAvailable");
  const titleKey = Object.prototype.hasOwnProperty.call(
    businessEventTranslationKeys,
    eventType,
  ) ? businessEventTranslationKeys[eventType] : "timelineEventGeneric";
  const typeCode = textElement("code", eventType);
  typeCode.setAttribute("aria-label", `${t("eventTypeCode")}: ${eventType}`);
  heading.append(textElement("h4", t(titleKey)), typeCode);

  const occurredAt = primitiveBusinessValue(event?.occurred_at);
  const time = textElement("time", formatDate(occurredAt));
  if (occurredAt !== null) {
    time.dateTime = occurredAt;
    time.title = occurredAt;
  }
  header.append(heading, time);
  card.append(header);

  const metadata = textElement("dl", null, "business-event-metadata");
  const actorId = primitiveBusinessValue(event?.actor?.id);
  const actorType = primitiveBusinessValue(event?.actor?.type);
  const actor = actorId === null
    ? null
    : `${actorId}${actorType === null ? "" : ` · ${actorType}`}`;
  appendTimelineFact(metadata, t("eventIdentifier"), event?.event_id, "code-value");
  appendTimelineFact(metadata, t("eventActor"), actor, "code-value");
  appendTimelineFact(metadata, t("eventCorrelation"), event?.correlation_id, "code-value");
  card.append(metadata);

  const payload = allowedBusinessPayload(event?.payload);
  const details = textElement("dl", null, "business-event-details");
  let detailCount = 0;
  if (payload.from_status !== undefined || payload.to_status !== undefined) {
    const from = localizedCode(payload.from_status, translatedStatus);
    const to = localizedCode(payload.to_status, translatedStatus);
    const transition = from && to ? `${from} → ${to}` : (from ?? to);
    detailCount += Number(appendTimelineFact(details, t("eventStateChange"), transition));
  }
  detailCount += Number(appendTimelineFact(
    details,
    t("eventOutcome"),
    localizedCode(payload.outcome, translatedOutcome),
  ));
  detailCount += Number(appendTimelineFact(
    details,
    t("eventReasonOriginal"),
    payload.reason,
    "source-value",
  ));
  detailCount += Number(appendTimelineFact(details, t("eventRequestVersion"), payload.request_version));
  detailCount += Number(appendTimelineFact(details, t("eventPolicyVersion"), payload.policy_version, "code-value"));
  detailCount += Number(appendTimelineFact(details, t("eventRoute"), payload.route, "code-value"));
  detailCount += Number(appendTimelineFact(details, t("eventDecisionId"), payload.decision_id, "code-value"));
  detailCount += Number(appendTimelineFact(
    details,
    t("eventAutomatedDecisionId"),
    payload.automated_decision_id,
    "code-value",
  ));
  detailCount += Number(appendTimelineFact(
    details,
    t("eventExtractionStatus"),
    payload.extraction_status,
    "code-value",
  ));
  detailCount += Number(appendTimelineFact(
    details,
    t("eventAttachmentCount"),
    payload.attachment_count,
  ));

  if (detailCount) {
    card.append(details);
  } else {
    card.append(textElement("p", t("noTimelineDetails"), "business-event-empty-details"));
  }
  item.append(card);
  return item;
}

function renderBusinessTimeline() {
  elements["timeline-list"].replaceChildren();
  elements["timeline-count"].textContent = String(state.timelineItems.length);
  for (const event of state.timelineItems) {
    elements["timeline-list"].append(renderBusinessEvent(event));
  }
}

function updateTimelinePagination() {
  const canLoadMore = Boolean(
    state.timelinePage?.has_more && state.timelinePage?.next_cursor,
  );
  elements["timeline-load-more"].hidden = !canLoadMore;
  elements["timeline-load-more"].disabled = state.timelineLoadingMore;
  elements["timeline-load-more"].textContent = t(
    state.timelineLoadingMore ? "loadingMoreEvents" : "loadMoreEvents",
  );
  elements["timeline-section"].setAttribute(
    "aria-busy",
    String(state.timelineMode === "loading" || state.timelineLoadingMore),
  );
}

function setTimelineState(mode, errorKey = null) {
  state.timelineMode = mode;
  if (errorKey) state.timelineErrorKey = errorKey;
  if (mode !== "error") state.timelineErrorKey = null;
  const hasEvents = state.timelineItems.length > 0;
  elements["timeline-loading"].hidden = mode !== "loading";
  elements["timeline-error"].hidden = mode !== "error";
  elements["timeline-empty"].hidden = mode !== "empty";
  elements["timeline-content"].hidden = !(mode === "content" || (mode === "error" && hasEvents));
  if (mode === "error") {
    elements["timeline-error-message"].textContent = t(
      state.timelineErrorKey ?? "timelineErrorMessage",
    );
  }
  updateTimelinePagination();
}

function timelineErrorKey(error) {
  if (error?.status === 401) return "sessionExpired";
  if (error?.status === 403) return "accessDenied";
  if (error?.status === 429 || error?.status >= 500) return "serviceUnavailable";
  return "timelineErrorMessage";
}

function normalizeTimelineResponse(body) {
  const items = Array.isArray(body?.items) ? body.items : [];
  const page = body?.page && typeof body.page === "object" ? body.page : {};
  const nextCursor = typeof page.next_cursor === "string" && page.next_cursor.trim()
    ? page.next_cursor
    : null;
  return {
    items,
    page: {
      limit: Number.isInteger(page.limit) ? page.limit : 25,
      has_more: Boolean(page.has_more && nextCursor),
      next_cursor: nextCursor,
    },
  };
}

function appendUniqueTimelineEvents(events) {
  const seen = new Set(
    state.timelineItems
      .map((event) => primitiveBusinessValue(event?.event_id))
      .filter((eventId) => eventId !== null),
  );
  for (const event of events) {
    const eventId = primitiveBusinessValue(event?.event_id);
    if (eventId !== null && seen.has(eventId)) continue;
    state.timelineItems.push(event);
    if (eventId !== null) seen.add(eventId);
  }
}

async function loadBusinessTimeline(requestId, { append = false } = {}) {
  if (!requestId || state.timelineLoadingMore) return;
  if (append && (!state.timelinePage?.has_more || !state.timelinePage?.next_cursor)) return;
  if (state.timelineController) state.timelineController.abort();

  const cursor = append ? state.timelinePage.next_cursor : null;
  const controller = new AbortController();
  state.timelineController = controller;
  if (append) {
    state.timelineLoadingMore = true;
    updateTimelinePagination();
  } else {
    state.timelineItems = [];
    state.timelinePage = { limit: 25, has_more: false, next_cursor: null };
    renderBusinessTimeline();
    setTimelineState("loading");
  }

  const params = new URLSearchParams({ limit: "25" });
  if (cursor) params.set("cursor", cursor);
  try {
    const { body } = await api(
      `/api/reviews/${encodeURIComponent(requestId)}/events?${params.toString()}`,
      { signal: controller.signal },
    );
    if (controller.signal.aborted || state.selectedRequestId !== requestId) return;
    const normalized = normalizeTimelineResponse(body);
    if (append) {
      appendUniqueTimelineEvents(normalized.items);
    } else {
      state.timelineItems = [];
      appendUniqueTimelineEvents(normalized.items);
    }
    state.timelinePage = normalized.page;
    state.timelineLoadingMore = false;
    renderBusinessTimeline();
    setTimelineState(state.timelineItems.length ? "content" : "empty");
    announce(t(state.timelineItems.length === 1 ? "timelineLoadedOne" : "timelineLoaded", {
      count: state.timelineItems.length,
    }));
  } catch (error) {
    if (error?.name === "AbortError" || state.selectedRequestId !== requestId) return;
    state.timelineLoadingMore = false;
    setTimelineState("error", timelineErrorKey(error));
  } finally {
    if (state.timelineController === controller) state.timelineController = null;
    if (state.selectedRequestId === requestId) {
      state.timelineLoadingMore = false;
      updateTimelinePagination();
    }
  }
}

function renderAttachments(attachments) {
  elements["attachment-list"].replaceChildren();
  elements["attachment-count"].textContent = String(attachments.length);
  elements["attachment-count-summary"].textContent = String(attachments.length);
  for (const attachment of attachments) {
    const item = textElement("li", null, "attachment-item");
    item.append(textElement("span", "▧"), textElement("span", attachment.location ?? attachment));
    elements["attachment-list"].append(item);
  }
  if (!attachments.length) {
    const item = textElement("li", null, "attachment-item");
    item.append(textElement("span", "▧"), textElement("span", t("noAttachments")));
    elements["attachment-list"].append(item);
  }
}

function updateReasonCounter() {
  elements["reason-counter"].textContent = `${elements["decision-reason"].value.length} / 2000`;
}

function hasMandatoryRejection(caseData = state.selectedCase) {
  const rules = caseData?.automated_decision?.rule_evaluations;
  return Array.isArray(rules) && rules.some((rule) => rule?.outcome === "reject");
}

function renderCase(caseData, { preserveReason = false } = {}) {
  const existingReason = preserveReason ? elements["decision-reason"].value : "";
  state.selectedCase = caseData;
  elements["request-id"].textContent = caseData.request_id ?? "—";
  elements["case-submitted"].textContent = t("submittedAt", { date: formatDate(caseData.submitted_at) });
  elements["case-status"].textContent = translatedStatus(caseData.status);
  elements["submitted-by"].textContent = caseData.submitted_by ?? t("notAvailable");
  elements["policy-version"].textContent = caseData.automated_decision?.policy_version ?? "—";
  elements["case-pending-since"].textContent = formatDate(caseData.pending_since ?? caseData.submitted_at);
  elements["ocr-text"].textContent = caseData.raw_ocr_text || t("noOcr");
  renderComparison(caseData);
  renderProblems(caseData.problems ?? []);
  renderFacts(caseData.extraction?.facts ?? null);
  renderRules(caseData.automated_decision?.rule_evaluations ?? []);
  renderAttachments(caseData.attachments ?? []);
  elements["decision-reason"].value = existingReason;
  updateReasonCounter();
  const isPending = caseData.status === "pending_review";
  const approvalBlocked = isPending && hasMandatoryRejection(caseData);
  elements["decision-panel"].hidden = !isPending;
  elements["mandatory-rejection-notice"].hidden = !approvalBlocked;
  elements["approve-button"].disabled = approvalBlocked;
  const decisionNav = document.querySelector('.detail-nav a[href="#decision-panel"]');
  if (decisionNav) decisionNav.hidden = !isPending;
  setDetailState("content");
}

async function loadCase(requestId, trigger = null) {
  state.lastCaseTrigger = trigger ?? state.lastCaseTrigger;
  state.selectedRequestId = requestId;
  state.selectedEtag = null;
  state.selectedCase = null;
  elements["request-id"].textContent = requestId;
  openCaseDialog();
  setDetailState("loading");
  void loadBusinessTimeline(requestId);
  renderTable(state.queueItems);
  renderCards(state.queueItems);
  try {
    const { body, response } = await api(`/api/reviews/${encodeURIComponent(requestId)}`);
    if (state.selectedRequestId !== requestId) return;
    state.selectedEtag = response.headers.get("etag");
    renderCase(body);
  } catch (error) {
    if (state.selectedRequestId !== requestId) return;
    setDetailState("error", localizedApiError(error, "detail"));
  }
}

function renderConfirmation(outcome) {
  const approving = outcome === "approved";
  elements["confirm-title"].textContent = t(approving ? "confirmApprove" : "confirmReject");
  elements["confirm-copy"].textContent = t(approving ? "confirmApproveCopy" : "confirmRejectCopy", {
    id: state.selectedRequestId,
  });
  elements["confirm-icon"].textContent = approving ? "✓" : "×";
  elements["confirm-icon"].classList.toggle("reject", !approving);
  elements["confirm-button"].textContent = t(approving ? "confirmApprove" : "confirmReject");
  elements["confirm-button"].className = approving ? "button button-success" : "button button-danger";
}

function requestDecision(outcome) {
  if (outcome === "approved" && hasMandatoryRejection()) return;
  const reason = elements["decision-reason"].value.trim();
  if (!reason) {
    showToast(t("rationaleRequired"), true);
    elements["decision-reason"].focus();
    return;
  }
  state.pendingOutcome = outcome;
  renderConfirmation(outcome);
  elements["confirm-dialog"].returnValue = "";
  elements["confirm-dialog"].showModal();
  syncBodyDialogState();
}

function setDecisionBusy(busy) {
  state.deciding = busy;
  elements["approve-button"].disabled = busy || hasMandatoryRejection();
  elements["reject-button"].disabled = busy;
  elements["confirm-button"].disabled = busy;
}

async function submitDecision() {
  if (state.deciding || !state.pendingOutcome || !state.selectedRequestId) return;
  const requestId = state.selectedRequestId;
  setDecisionBusy(true);
  try {
    const { body } = await api(`/api/reviews/${encodeURIComponent(requestId)}/decisions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "If-Match": state.selectedEtag,
        "X-CSRF-Token": state.csrfToken,
      },
      body: JSON.stringify({
        outcome: state.pendingOutcome,
        reason: elements["decision-reason"].value.trim(),
      }),
    });
    if (elements["confirm-dialog"].open) elements["confirm-dialog"].close();
    showToast(t("decisionRecorded", { eventId: body?.audit_event_id ?? "—" }));
    await Promise.all([
      loadCase(requestId),
      loadQueue({ announceResult: false }),
    ]);
    if (!state.queueItems.length && state.cursorHistory.length) {
      state.cursor = state.cursorHistory.pop();
      state.pageNumber -= 1;
      await loadQueue({ announceResult: false });
    }
  } catch (error) {
    if (elements["confirm-dialog"].open) elements["confirm-dialog"].close();
    if (error.status === 409 || error.status === 412) {
      showToast(t("caseChanged"), true);
      await Promise.all([loadCase(requestId), loadQueue({ announceResult: false })]);
    } else {
      showToast(error.status ? localizedApiError(error, "detail") : t("decisionFailed"), true);
    }
  } finally {
    state.pendingOutcome = null;
    setDecisionBusy(false);
    syncBodyDialogState();
  }
}

function rerenderForLanguage() {
  applyTranslations();
  if (state.queueMode === "results" || state.queueMode === "empty") {
    renderQueue();
  } else {
    renderActiveFilters();
    renderMetrics(state.summary, state.queueItems);
    renderPagination();
  }
  if (state.selectedCase) renderCase(state.selectedCase, { preserveReason: true });
  if (state.timelineMode !== "idle") {
    renderBusinessTimeline();
    setTimelineState(state.timelineMode, state.timelineErrorKey);
  }
  if (elements["confirm-dialog"].open && state.pendingOutcome) {
    renderConfirmation(state.pendingOutcome);
  }
  updateView();
}

elements["language-select"].addEventListener("change", (event) => {
  state.language = event.target.value;
  rerenderForLanguage();
});

elements["refresh-queue"].addEventListener("click", () => loadQueue());
elements["retry-queue"].addEventListener("click", () => loadQueue());
elements["empty-reset-filters"].addEventListener("click", clearFilters);
elements["reset-filters"].addEventListener("click", clearFilters);
elements["clear-active-filters"].addEventListener("click", clearFilters);

elements["filter-toggle"].addEventListener("click", () => {
  const opening = elements["filter-panel"].hidden;
  elements["filter-panel"].hidden = !opening;
  elements["filter-toggle"].setAttribute("aria-expanded", String(opening));
  if (opening) elements["category-filter"].focus();
});

elements["filter-form"].addEventListener("submit", (event) => {
  event.preventDefault();
  applyFilters();
});

elements["search-input"].addEventListener("input", (event) => {
  window.clearTimeout(searchTimer);
  const value = event.target.value.trim();
  searchTimer = window.setTimeout(() => {
    if (state.filters.search === value) return;
    state.filters.search = value;
    resetPagination();
    renderActiveFilters();
    loadQueue();
  }, 350);
});

elements["sort-select"].addEventListener("change", (event) => {
  state.filters.sort = event.target.value;
  resetPagination();
  loadQueue();
});

elements["page-size-select"].addEventListener("change", (event) => {
  state.filters.limit = Number(event.target.value);
  resetPagination();
  loadQueue();
});

elements["table-view-button"].addEventListener("click", () => {
  state.view = "table";
  updateView(true);
});

elements["card-view-button"].addEventListener("click", () => {
  state.view = "cards";
  updateView(true);
});

elements["previous-page"].addEventListener("click", async () => {
  if (!state.cursorHistory.length) return;
  state.cursor = state.cursorHistory.pop();
  state.pageNumber -= 1;
  await loadQueue();
  document.getElementById("worklist-title").focus?.();
});

elements["next-page"].addEventListener("click", async () => {
  if (!state.page?.has_more || !state.page?.next_cursor) return;
  state.cursorHistory.push(state.cursor);
  state.cursor = state.page.next_cursor;
  state.pageNumber += 1;
  await loadQueue();
  document.getElementById("worklist-title").focus?.();
});

elements["close-case"].addEventListener("click", () => elements["case-dialog"].close());
elements["retry-detail"].addEventListener("click", () => {
  if (state.selectedRequestId) loadCase(state.selectedRequestId);
});
elements["retry-timeline"].addEventListener("click", () => {
  if (state.selectedRequestId) {
    void loadBusinessTimeline(state.selectedRequestId, {
      append: state.timelineItems.length > 0,
    });
  }
});
elements["timeline-load-more"].addEventListener("click", () => {
  if (state.selectedRequestId) {
    void loadBusinessTimeline(state.selectedRequestId, { append: true });
  }
});
elements["decision-reason"].addEventListener("input", updateReasonCounter);
elements["approve-button"].addEventListener("click", () => requestDecision("approved"));
elements["reject-button"].addEventListener("click", () => requestDecision("rejected"));

elements["confirm-dialog"].addEventListener("close", () => {
  syncBodyDialogState();
  if (elements["confirm-dialog"].returnValue === "confirm") {
    submitDecision();
  } else {
    state.pendingOutcome = null;
  }
});

elements["case-dialog"].addEventListener("close", () => {
  if (state.timelineController) {
    state.timelineController.abort();
    state.timelineController = null;
  }
  syncBodyDialogState();
  if (state.lastCaseTrigger?.isConnected) state.lastCaseTrigger.focus();
});

document.addEventListener("keydown", (event) => {
  const target = event.target;
  const editing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement;
  if (event.key === "/" && !editing && !elements["case-dialog"].open && !elements["confirm-dialog"].open) {
    event.preventDefault();
    elements["search-input"].focus();
  }
  if (event.key.toLowerCase() === "r" && !editing && !elements["case-dialog"].open && !elements["confirm-dialog"].open) {
    event.preventDefault();
    loadQueue();
  }
});

async function start() {
  applyTranslations();
  syncFilterControls();
  updateView();
  renderActiveFilters();
  try {
    await loadSession();
    await loadQueue({ announceResult: false });
  } catch (error) {
    setQueueState("error", localizedApiError(error, "queue"));
  }
}

start();
