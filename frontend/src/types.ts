export type NucleusState = "active" | "hidden" | "excluded";

export interface SelectionModifiers {
  additive: boolean;
  range: boolean;
}

export interface Nucleus {
  nucleus_id: number;
  area_px: number;
  area_um2: number | null;
  centroid_x: number;
  centroid_y: number;
  bounding_box: { x: number; y: number; width: number; height: number };
  perimeter_px: number | null;
  equivalent_radius_px: number | null;
  equivalent_diameter_px: number | null;
  major_axis_px: number | null;
  minor_axis_px: number | null;
  eccentricity: number | null;
  circularity: number | null;
  nucleus_mean: number | null;
  nucleus_median: number | null;
  nucleus_std: number | null;
  nucleus_integrated: number | null;
  protein_mean: number | null;
  protein_median: number | null;
  protein_std: number | null;
  protein_integrated: number | null;
  state: NucleusState;
  polygon: [number, number][];
}

export interface Config {
  nucleus_channel: number; protein_channel: number; gaussian_kernel: number; gaussian_sigma: number;
  opening_kernel: number; closing_kernel: number; min_nucleus_area: number;
  pixel_size: number | null; pixel_unit: string; input_mode: "auto" | "raw" | "derived";
}
export interface ImageDescriptor { name: string; role: "nucleus" | "protein"; width: number; height: number; channels: number; dtype: string; derived: boolean; }
export interface Session { session_id: string; job_id: string; status: string; revision: number; config: Config; warnings: string[]; images: ImageDescriptor[]; }
export interface Result { session_id: string; revision: number; status: string; config: Config; warnings: string[]; shape: { width: number; height: number } | null; nuclei: Nucleus[]; aggregate: Record<string, number | null>; job_id: string; }
export interface Job { job_id: string; session_id: string; status: string; progress: number; message: string; error: string | null; }
