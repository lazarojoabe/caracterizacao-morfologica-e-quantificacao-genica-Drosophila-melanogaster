export type Point = [number, number];
export interface Transform { scale: number; x: number; y: number; }
export function screenToImage(point: Point, transform: Transform): Point { return [(point[0] - transform.x) / transform.scale, (point[1] - transform.y) / transform.scale]; }
export function imageToScreen(point: Point, transform: Transform): Point { return [point[0] * transform.scale + transform.x, point[1] * transform.scale + transform.y]; }
export function zoomAt(transform: Transform, cursor: Point, factor: number): Transform { const nextScale = Math.min(20, Math.max(0.05, transform.scale * factor)); const image = screenToImage(cursor, transform); return { scale: nextScale, x: cursor[0] - image[0] * nextScale, y: cursor[1] - image[1] * nextScale }; }
export function pointInPolygon(point: Point, polygon: Point[]): boolean { let inside = false; for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) { const [xi, yi] = polygon[i], [xj, yj] = polygon[j]; const intersect = yi > point[1] !== yj > point[1] && point[0] < ((xj - xi) * (point[1] - yi)) / (yj - yi) + xi; if (intersect) inside = !inside; } return inside; }
