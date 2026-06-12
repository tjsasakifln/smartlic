import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { AlertConfig, PredictiveAlert } from "../../app/radar/components/AlertConfig";

const alerts: PredictiveAlert[] = [
  {id:"a1",sector_id:"saude",alert_type:"volume_spike",threshold_value:50000,uf:"SP",enabled:true,last_triggered_at:"2026-06-11T10:00:00Z",created_at:"2026-06-10T10:00:00Z",updated_at:"2026-06-11T10:00:00Z"},
  {id:"a2",sector_id:"educacao",alert_type:"new_opportunity",threshold_value:0,uf:null,enabled:false,last_triggered_at:null,created_at:"2026-06-09T10:00:00Z",updated_at:"2026-06-09T10:00:00Z"},
];

describe("AlertConfig", () => {
  it("renders loading skeleton", () => {
    render(<AlertConfig alerts={[]} loading />);
    expect(screen.getByTestId("alert-config-skeleton")).toBeInTheDocument();
  });
  it("renders empty state", () => {
    render(<AlertConfig alerts={[]} />);
    expect(screen.getByTestId("alert-config-empty")).toBeInTheDocument();
  });
  it("renders error state with retry", () => {
    const r = jest.fn();
    render(<AlertConfig alerts={[]} error="Erro" onRetry={r} />);
    expect(screen.getByTestId("alert-config-error")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Tentar novamente"));
    expect(r).toHaveBeenCalled();
  });
  it("renders alert list", () => {
    render(<AlertConfig alerts={alerts} />);
    expect(screen.getByTestId("alert-config")).toBeInTheDocument();
    expect(screen.getByText("Pico de volume")).toBeInTheDocument();
    expect(screen.getByText("Nova oportunidade")).toBeInTheDocument();
  });
  it("shows sector and UF badges", () => {
    render(<AlertConfig alerts={alerts} />);
    expect(screen.getByText("saude")).toBeInTheDocument();
    expect(screen.getByText("SP")).toBeInTheDocument();
  });
  it("shows create form on add click", () => {
    render(<AlertConfig alerts={[]} onCreate={jest.fn()} availableSectors={["s1"]}/>);
    fireEvent.click(screen.getByTestId("alert-config-add-button"));
    expect(screen.getByTestId("create-alert-form")).toBeInTheDocument();
  });
  it("calls onCreate with data", () => {
    const fn = jest.fn();
    render(<AlertConfig alerts={[]} onCreate={fn} availableSectors={["saude"]}/>);
    fireEvent.click(screen.getByTestId("alert-config-add-button"));
    fireEvent.change(screen.getByTestId("create-alert-sector"),{target:{value:"saude"}});
    fireEvent.change(screen.getByTestId("create-alert-type"),{target:{value:"volume_spike"}});
    fireEvent.change(screen.getByTestId("create-alert-threshold"),{target:{value:"50000"}});
    fireEvent.change(screen.getByTestId("create-alert-uf"),{target:{value:"RJ"}});
    fireEvent.click(screen.getByTestId("create-alert-submit"));
    expect(fn).toHaveBeenCalledWith({sector_id:"saude",alert_type:"volume_spike",threshold_value:50000,uf:"RJ"});
  });
  it("calls onToggle", () => {
    const fn = jest.fn();
    render(<AlertConfig alerts={alerts} onToggle={fn}/>);
    fireEvent.click(screen.getByTestId("alert-toggle-a1"));
    expect(fn).toHaveBeenCalledWith("a1",false);
  });
  it("calls onDelete", () => {
    const fn = jest.fn();
    render(<AlertConfig alerts={alerts} onDelete={fn}/>);
    fireEvent.click(screen.getByTestId("alert-delete-a1"));
    expect(fn).toHaveBeenCalledWith("a1");
  });
  it("shows disabled state", () => {
    render(<AlertConfig alerts={alerts} />);
    expect(screen.getByTestId("alert-card-a2").className).toContain("opacity-60");
  });
  it("has aria-labels", () => {
    render(<AlertConfig alerts={alerts} onToggle={jest.fn()} onDelete={jest.fn()}/>);
    expect(screen.getByLabelText("Desativar alerta")).toBeInTheDocument();
    expect(screen.getByLabelText("Ativar alerta")).toBeInTheDocument();
    expect(screen.getAllByLabelText("Remover alerta")).toHaveLength(2);
  });
});
