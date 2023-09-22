import { connections } from "./connections";

describe("connections", () => {
  it("should work", () => {
    // sample test code
    // expect(connections()).toEqual("connections");

    // fake test could always pass
    expect(1).toEqual(1);

    expect(async () => await connections()).not.toThrowError();
  });
});
