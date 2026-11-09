export interface User {
  id: number;
  username: string;
  full_name: string;
  role: string;
  role_label: string;
}

export interface CaseSummary {
  id: number;
  case_no: string;
  brand: string;
  series: string;
  vehicle_year: number | null;
  trim: string;
  region_code: string;
  region_name: string;
  status: string;
  status_label: string;
  created_by_name: string;
  created_at: string;
  updated_at: string;
  image_count: number;
  damage_count: number;
  latest_quote: {
    id: number;
    quote_no: string;
    status: string;
    total_low: number;
    total_mid: number;
    total_high: number;
    created_at: string;
  } | null;
}

export interface CaseImage {
  id: number;
  case_id: number;
  filename: string;
  original_name: string;
  url: string;
  overlay_url: string | null;
  width: number;
  height: number;
  model_name: string | null;
  created_at: string;
}

export interface Suggestion {
  severity_band: string;
  severity_label: string;
  action: string | null;
  action_label: string | null;
  method: string | null;
  rule_code: string | null;
  requires_review: boolean;
}

export interface Damage {
  id: number;
  case_id: number;
  image_id: number;
  class_name: string;
  class_label: string;
  class_id: number;
  confidence: number;
  bbox: number[];
  polygons: number[][][];
  mask_area_ratio: number;
  needs_review: boolean;
  part_code: string | null;
  part_name: string | null;
  severity_band: string | null;
  severity_label: string;
  action: string | null;
  action_label: string;
  method: string | null;
  note: string | null;
  confirmed: boolean;
  confirmed_by: string | null;
  confirmed_at: string | null;
  updated_at: string;
  suggestion?: Suggestion;
}

export interface CaseDetail extends CaseSummary {
  images: CaseImage[];
  damages: Damage[];
}

export interface QuoteItem {
  id: number;
  damage_id: number;
  part_code: string;
  part_name: string;
  action: string;
  action_label: string;
  method: string;
  severity_band: string;
  severity_label: string;
  part_price: number;
  material_cost: number;
  standard_hours: number;
  labor_rate: number;
  labor_coefficient: number;
  labor_amount: number;
  subtotal_low: number;
  subtotal: number;
  subtotal_high: number;
  rule_code: string;
  requires_review: boolean;
  note: string | null;
}

export interface Quote {
  id: number;
  quote_no: string;
  case_id: number;
  pricing_rule_version: number;
  formula_version: string;
  status: string;
  total_low: number;
  total_mid: number;
  total_high: number;
  region_code: string;
  region_name: string;
  labor_rate: number;
  labor_coefficient: number;
  manual_override_reason: string | null;
  created_by_name: string;
  created_at: string;
  confirmed_by: string | null;
  confirmed_at: string | null;
  hit_rules: Array<Record<string, unknown>>;
  items: QuoteItem[];
}

export interface QuotePreviewItem {
  damage_id: number;
  part_name: string;
  action_label: string;
  method: string;
  severity_label: string;
  subtotal: number;
  requires_review: boolean;
}

export interface QuotePreview {
  case_id: number;
  ready: boolean;
  pending_count: number;
  total_low: number;
  total_mid: number;
  total_high: number;
  items: QuotePreviewItem[];
}

export interface Report {
  id: number;
  report_no: string;
  case_id: number;
  quote_id: number;
  html_url: string;
  file_url?: string;
  generated_by: string;
  generated_at: string;
}

export interface PartRow {
  id: number;
  vehicle_model_id: number | null;
  vehicle_year: number | null;
  part_code: string;
  part_name: string;
  category: string;
  paintable: boolean;
  replaceable: boolean;
  price_low: number;
  list_price: number;
  price_high: number;
  currency: string;
  version: number;
}

export interface LaborRow {
  id: number;
  part_code: string | null;
  damage_type: string | null;
  action: string;
  severity_band: string;
  standard_hours: number;
  version: number;
}

export interface MaterialRow {
  id: number;
  part_code: string | null;
  action: string;
  severity_band: string;
  material_cost: number;
  version: number;
}

export interface RegionRow {
  id: number;
  region_code: string;
  region_name: string;
  labor_rate: number;
  coefficient: number;
  version: number;
}

export interface RuleRow {
  id: number;
  rule_code: string;
  priority: number;
  damage_type: string;
  part_category: string[] | null;
  area_ratio_min: number;
  area_ratio_max: number | null;
  action: string;
  method: string;
  requires_review: boolean;
  formula_version: string;
  version: number;
}

export interface ThresholdRow {
  id: number;
  damage_type: string;
  minor_max: number;
  severe_min: number;
  version: number;
}

export interface Catalog {
  formula: string;
  labels: {
    damage_types: Record<string, string>;
    actions: Record<string, string>;
    severities: Record<string, string>;
  };
  vehicle_models: Array<Record<string, unknown>>;
  parts: PartRow[];
  labor: LaborRow[];
  materials: MaterialRow[];
  regions: RegionRow[];
  rules: RuleRow[];
  thresholds: ThresholdRow[];
}

export interface ModelVersion {
  id: number;
  name: string;
  weights_path: string;
  metrics: {
    overall_mask_map50_95?: number;
    overall_mask_map50?: number;
    overall_box_map50_95?: number;
    per_class_mask_ap50_95?: Record<string, number | null>;
    parameters?: number;
    latency_ms?: { p50?: number; p95?: number };
  } | null;
  train_config: Record<string, unknown> | null;
  dataset_hash: string | null;
  is_active: boolean;
  created_at: string;
}
