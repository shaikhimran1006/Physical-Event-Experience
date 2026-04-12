describe("Dashboard smoke", () => {
  it("loads command center and navigates to queue monitor", () => {
    cy.visit("/");
    cy.contains("Command Center").should("be.visible");

    cy.contains("button", "Queue Monitor").click();
    cy.contains("Queue Monitor").should("be.visible");
  });
});
