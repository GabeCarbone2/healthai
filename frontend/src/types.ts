export type FieldOption = {
  value: string;
  label: string;
};

export type InputField = {
  key: string;
  label: string;
  unit?: string;
  type: "number" | "select";
  min?: number;
  max?: number;
  step?: number;
  required?: boolean;
  options?: FieldOption[];
};

export type CrossValidation = {
  mean: number;
  std: number;
  fold_scores: number[];
};

export type ClassificationMetrics = {
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  roc_auc: number | null;
  brier_score: number;
  confusion_matrix: number[][];
};

export type ConfidenceIntervals = {
  method: string;
  dataset: string;
  confidence_level: number;
  n_bootstrap: number;
  random_state: number;
  metrics: Record<
    string,
    {
      estimate: number;
      lower: number;
      upper: number;
      valid_resamples: number;
    } | null
  >;
};

export type ModelMetrics = ClassificationMetrics & {
  calibration: {
    dataset: string;
    strategy: string;
    requested_bins: number;
    effective_bins: number;
    expected_calibration_error: number;
    points: Array<{
      bin_lower: number;
      bin_upper: number;
      mean_predicted_probability: number;
      observed_frequency: number;
      count: number;
    }>;
  };
  confidence_intervals: ConfidenceIntervals | null;
  subgroups: Record<
    string,
    {
      column: string;
      label: string;
      dataset: string;
      minimum_size: number;
      minimum_events: number;
      n_total: number;
      missing_or_unassigned: number;
      groups: Array<{
        value: string;
        label: string;
        n: number;
        positives: number;
        prevalence: number | null;
        status: "estimated" | "limited_events" | "insufficient_sample";
        minimum_size?: number;
        minimum_events?: number;
        metrics: ClassificationMetrics | null;
        confidence_intervals: ConfidenceIntervals | null;
      }>;
    }
  >;
  cross_validation: CrossValidation;
  threshold: {
    metric: string;
    beta: number;
    value: number;
    f_beta: number;
    precision: number;
    recall: number;
  };
};

export type Experiment = {
  id: "pima" | "nhanes";
  label: string;
  selected_model: string;
  selected_model_label: string;
  source_dataset: string;
  n_train: number;
  n_test: number;
  selection: {
    metric: string;
    cv_folds: number;
    scope: string;
  };
  models: Record<string, ModelMetrics>;
  input_fields: InputField[];
};

export type Catalog = {
  experiments: Experiment[];
  model_labels: Record<string, string>;
};

export type Prediction = {
  experiment: string;
  model: string;
  predicted_class: number;
  probability: number;
  decision_threshold: number;
};

export type User = {
  id: number;
  email: string;
  name: string;
  role: string;
  created_at: string;
  email_verified_at: string | null;
  privacy_accepted_at: string | null;
  privacy_notice_version: string | null;
};

export type RegistrationResponse = {
  email: string;
  verification_required: true;
  expires_in_seconds: number;
  email_sent: boolean;
};

export type PatientResult = {
  id: number;
  patientIdentifier: string;
  createdAt: string;
  experiment: string;
  model: string;
  predictedClass: number;
  probability: number;
  decisionThreshold: number;
};

export type StoredPatientResult = {
  id: number;
  patient_identifier: string;
  created_at: string;
  experiment: string;
  model: string;
  predicted_class: number;
  probability: number;
  decision_threshold: number;
};

export type ResultFilters = {
  search: string;
  dateFrom: string;
  dateTo: string;
};

export type PatientResultPage = {
  items: PatientResult[];
  total: number;
  page: number;
  pageSize: number;
  pages: number;
};

export type StoredPatientResultPage = {
  items: StoredPatientResult[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type PrivacyInfo = {
  notice_version: string;
  result_retention_days: number;
  contact: string;
};
