describe("Fan app smoke", () => {
  it("loads home recommendations and navigates tabs", () => {
    cy.visit("/");

    cy.contains("Best Gate").should("be.visible");

    cy.contains("button", "Queues").click();
    cy.contains("Gates").should("be.visible");

    cy.contains("button", "Alerts").click();
    cy.contains("Notifications").should("be.visible");
  });
});
