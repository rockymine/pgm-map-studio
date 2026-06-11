import { describe, it, expect } from "vitest";
import {
  nextTeamColor,
  TEAM_COLOR_PRIORITY,
} from "../../src/pgm_map_studio/studio/static/shared/game-colors.js";

describe("nextTeamColor (C11 — auto team colour/id defaults)", () => {
  it("picks red for the first team (no colours used)", () => {
    expect(nextTeamColor([]).value).toBe("red");
  });

  it("picks the next unused colour in priority order", () => {
    expect(nextTeamColor(["red"]).value).toBe("blue");
    expect(nextTeamColor(["red", "blue"]).value).toBe("green");
    expect(nextTeamColor(["red", "blue", "green"]).value).toBe("yellow");
  });

  it("skips already-used colours regardless of slot order", () => {
    // blue taken but red free → still red first
    expect(nextTeamColor(["blue"]).value).toBe("red");
  });

  it("normalizes underscore / case forms of stored colours", () => {
    // an imported team with `dark_blue` must count as the "dark blue" slot
    expect(nextTeamColor(["RED", "Blue"]).value).toBe("green");
    const used = TEAM_COLOR_PRIORITY.map(v => v.replace(/ /g, "_").toUpperCase());
    expect(nextTeamColor(used)).toBeNull();   // all 16 used → null
  });

  it("priority list is exactly the 16 chat colours", () => {
    expect(new Set(TEAM_COLOR_PRIORITY).size).toBe(16);
  });
});
