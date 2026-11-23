import { describe, expect, it } from "vitest";
import { imageToScreen, screenToImage, zoomAt } from "./geometry";

describe("transformação do canvas", () => {
  it("mantém coordenadas da imagem ao converter ida e volta", () => {
    const transform = { scale: 2, x: 30, y: -4 };
    expect(screenToImage(imageToScreen([120, 80], transform), transform)).toEqual([120, 80]);
  });
  it("mantém o ponto sob o cursor durante o zoom", () => {
    const next = zoomAt({ scale: 1, x: 0, y: 0 }, [100, 80], 2);
    expect(screenToImage([100, 80], next)).toEqual([100, 80]);
  });
});
