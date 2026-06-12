/**
 * @jest-environment jsdom
 */
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ShareWithClient from "../../../app/consultoria/clientes/components/ShareWithClient";

const mockFetch = jest.fn();
global.fetch = mockFetch as jest.Mock;

describe("ShareWithClient", () => {
  const props = { resourceType: "busca" as const, resourceId: "r-123", onShareComplete: jest.fn() };

  beforeEach(() => jest.clearAllMocks());

  it("renders share button", () => {
    render(<ShareWithClient {...props} />);
    expect(screen.getByText("Compartilhar")).toBeInTheDocument();
  });

  it("shows dropdown with clients", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => [{ id: "c1", client_email: "a@b.com", status: "active" }] });
    render(<ShareWithClient {...props} />);
    fireEvent.click(screen.getByText("Compartilhar"));
    expect(await screen.findByText("a@b.com")).toBeInTheDocument();
  });

  it("calls share API on client click", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => [{ id: "c1", client_email: "a@b.com", status: "active" }] });
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => [{ id: "s1" }] });
    render(<ShareWithClient {...props} />);
    fireEvent.click(screen.getByText("Compartilhar"));
    await waitFor(() => expect(screen.getByText("a@b.com")).toBeInTheDocument());
    fireEvent.click(screen.getByText("a@b.com"));
    await waitFor(() => expect(mockFetch).toHaveBeenCalledWith("/api/consultoria/share/c1", expect.objectContaining({ method: "POST" })));
  });
});
