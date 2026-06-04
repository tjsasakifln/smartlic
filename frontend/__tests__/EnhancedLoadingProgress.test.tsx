/**
 * EnhancedLoadingProgress Component Tests
 * UX-411: Educational B2G carousel replacing technical stage indicators
 */

import React from 'react';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { EnhancedLoadingProgress } from '../app/buscar/components/EnhancedLoadingProgress';

describe('EnhancedLoadingProgress Component', () => {
  const mockOnStageChange = jest.fn();
  const mockOnCancel = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  describe('UX-411: Carousel renders tips', () => {
    it('should render at least 1 B2G tip in the carousel', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
        />
      );

      const carousel = screen.getByTestId('b2g-carousel');
      expect(carousel).toBeInTheDocument();

      const tip = screen.getByTestId('carousel-tip');
      expect(tip).toBeInTheDocument();
      expect(tip.textContent).toBeTruthy();
      // First tip should be the default
      expect(tip).toHaveTextContent(/trilhão em contratações públicas/);
    });

    it('should render dot indicators for all 15 tips', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
        />
      );

      const dots = screen.getByTestId('carousel-dots');
      const dotButtons = dots.querySelectorAll('button');
      expect(dotButtons).toHaveLength(15);
    });
  });

  describe('UX-411: Carousel rotates after 6 seconds', () => {
    it('should change tip after 6 seconds', async () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
        />
      );

      const tip = screen.getByTestId('carousel-tip');
      const firstTip = tip.textContent;

      // Advance 6s for interval + 300ms for fade transition
      act(() => {
        jest.advanceTimersByTime(6300);
      });

      await waitFor(() => {
        const currentTip = screen.getByTestId('carousel-tip');
        expect(currentTip.textContent).not.toBe(firstTip);
      });
    });

    it('should cycle through tips sequentially', async () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
        />
      );

      // Advance to second tip
      act(() => {
        jest.advanceTimersByTime(6300);
      });

      await waitFor(() => {
        expect(screen.getByTestId('carousel-tip')).toHaveTextContent(/Empate ficto/);
      });
    });
  });

  describe('UX-411: Progress bar without percentage', () => {
    it('should render progress bar without numeric percentage', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
        />
      );

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toBeInTheDocument();

      // No percentage text should exist in the component
      const percentageElements = screen.queryByText(/^\d+%$/);
      expect(percentageElements).not.toBeInTheDocument();
    });

    it('should animate progress bar width over time', async () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={10}
          stateCount={3}
          statesProcessed={2}
        />
      );

      const progressBar = screen.getByRole('progressbar');

      act(() => {
        jest.advanceTimersByTime(5000);
      });

      await waitFor(() => {
        const width = progressBar.style.width;
        const percentage = parseFloat(width);
        expect(percentage).toBeGreaterThan(0);
      });
    });

    it('should render gradient progress bar', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
        />
      );

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveClass('bg-gradient-to-r');
      expect(progressBar).toHaveClass('from-brand-blue');
      expect(progressBar).toHaveClass('to-brand-blue-hover');
    });
  });

  describe('UX-411: Spinner and text', () => {
    it('should show spinner and descriptive phase label (AC11)', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
        />
      );

      // DEBT-v3-S2 AC11: Phase labels replace static text
      const phaseLabels = ['Conectando fontes...', 'Analisando editais...', 'Classificando relevância...', 'Finalizando...'];
      const hasPhaseLabel = phaseLabels.some(label => screen.queryByText(label));
      expect(hasPhaseLabel).toBe(true);
      // SVG spinner should be present (with animate-spin class)
      const svg = document.querySelector('svg.animate-spin');
      expect(svg).toBeInTheDocument();
    });
  });

  describe('UX-411: Stage indicators removed', () => {
    it('should NOT have numbered stage indicators (1-5) in the DOM', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
        />
      );

      // No stage indicator circles with numbers 1-5
      for (let i = 1; i <= 5; i++) {
        // Check for standalone numbers used as stage indicators
        const elements = screen.queryAllByText(new RegExp(`^${i}$`));
        // Filter out carousel dot aria-labels
        const stageIndicators = elements.filter(el => {
          return el.closest('[class*="rounded-full"]') !== null &&
                 el.closest('[data-testid="carousel-dots"]') === null;
        });
        expect(stageIndicators).toHaveLength(0);
      }

      // No stage labels
      expect(screen.queryByText('Consultando fontes oficiais')).not.toBeInTheDocument();
      expect(screen.queryByText('Buscando dados')).not.toBeInTheDocument();
      expect(screen.queryByText('Filtrando resultados')).not.toBeInTheDocument();
      expect(screen.queryByText('Avaliando oportunidades')).not.toBeInTheDocument();
      expect(screen.queryByText('Preparando Excel')).not.toBeInTheDocument();
    });
  });

  describe('UX-411: Countdown removed', () => {
    it('should NOT show countdown text in the DOM', async () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
        />
      );

      act(() => {
        jest.advanceTimersByTime(10000);
      });

      await waitFor(() => {
        // No elapsed/estimated time display
        expect(screen.queryByText(/\d+s \/ ~\d+s/)).not.toBeInTheDocument();
        // No remaining time display
        expect(screen.queryByText(/~\d+s restantes/)).not.toBeInTheDocument();
        // No percentage display
        expect(screen.queryByText(/^\d+%$/)).not.toBeInTheDocument();
      });
    });
  });

  describe('UX-411 AC7: Overtime message', () => {
    it('should still show overtime message when elapsed exceeds estimated', async () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={10}
          stateCount={3}
        />
      );

      act(() => {
        jest.advanceTimersByTime(15000);
      });

      await waitFor(() => {
        expect(screen.getByTestId('overtime-message')).toBeInTheDocument();
        expect(screen.getByText(/Quase pronto, finalizando\.\.\./)).toBeInTheDocument();
      });
    });

    it('should show 2x overrun message', async () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={10}
          stateCount={3}
          statesProcessed={3}
        />
      );

      act(() => {
        jest.advanceTimersByTime(21000);
      });

      await waitFor(() => {
        expect(screen.getByText(/Esta busca está demorando mais que o normal/)).toBeInTheDocument();
      });
    });
  });

  describe('UX-411 AC8: Cancel button', () => {
    it('should render cancel button when onCancel is provided', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
          onCancel={mockOnCancel}
        />
      );

      const cancelButton = screen.getByText('Cancelar');
      expect(cancelButton).toBeInTheDocument();
    });

    it('should call onCancel when clicked', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
          onCancel={mockOnCancel}
        />
      );

      fireEvent.click(screen.getByText('Cancelar'));
      expect(mockOnCancel).toHaveBeenCalledTimes(1);
    });

    it('should not render cancel button when onCancel is not provided', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
        />
      );

      expect(screen.queryByText('Cancelar')).not.toBeInTheDocument();
    });
  });

  describe('UX-411 AC9: Degraded state', () => {
    it('should show amber scheme when isDegraded is true', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
          isDegraded={true}
        />
      );

      const container = screen.getByTestId('degraded-progress');
      expect(container).toBeInTheDocument();

      // Progress bar should have amber colors
      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveClass('from-amber-500');
      expect(progressBar).toHaveClass('to-amber-600');
    });

    it('should show degraded message', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
          isDegraded={true}
          degradedMessage="Dados de"
        />
      );

      expect(screen.getByTestId('degraded-message')).toBeInTheDocument();
      expect(screen.getByText('Dados de')).toBeInTheDocument();
    });

    it('should show default degraded message when no custom message', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
          isDegraded={true}
        />
      );

      expect(screen.getByText('Resultados disponíveis com ressalvas')).toBeInTheDocument();
    });
  });

  describe('UX-411 AC11: Hover pauses carousel', () => {
    it('should pause carousel on mouse enter and resume on mouse leave', async () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
        />
      );

      const carousel = screen.getByTestId('b2g-carousel');
      const tip = screen.getByTestId('carousel-tip');
      const firstTip = tip.textContent;

      // Hover over carousel
      fireEvent.mouseEnter(carousel);

      // Advance 12 seconds (2 full rotations normally)
      act(() => {
        jest.advanceTimersByTime(12000);
      });

      // Tip should NOT have changed during hover
      expect(screen.getByTestId('carousel-tip')).toHaveTextContent(firstTip!);

      // Mouse leave — carousel resumes
      fireEvent.mouseLeave(carousel);

      // Advance 6.3s (one rotation + fade)
      act(() => {
        jest.advanceTimersByTime(6300);
      });

      await waitFor(() => {
        expect(screen.getByTestId('carousel-tip').textContent).not.toBe(firstTip);
      });
    });
  });

  describe('UX-411 AC6: States processed display', () => {
    it('should show "X de Y estados processados"', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={5}
          statesProcessed={3}
        />
      );

      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText(/estados processados/)).toBeInTheDocument();
    });

    it('should show singular "estado processado" for count=1', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={1}
          statesProcessed={0}
        />
      );

      expect(screen.getByText(/Processando 1 estado$/)).toBeInTheDocument();
    });

    it('should show "Analisando em todo o Brasil" for 27 states', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={27}
        />
      );

      expect(screen.getByText(/Analisando em todo o Brasil/)).toBeInTheDocument();
    });
  });

  describe('UX-411 AC12: Props compatibility', () => {
    it('should accept all existing props without error', () => {
      expect(() =>
        render(
          <EnhancedLoadingProgress
            currentStep={1}
            estimatedTime={60}
            stateCount={3}
            onStageChange={mockOnStageChange}
            statesProcessed={2}
            onCancel={mockOnCancel}
            sseEvent={{ stage: 'fetching', progress: 35, message: 'Buscando...', detail: { uf_index: 2 } } as any}
            useRealProgress={true}
            sseDisconnected={false}
            ufAllComplete={false}
            isDegraded={false}
            degradedMessage=""
            showTimeoutOverlay={false}
            isReconnecting={false}
          />
        )
      ).not.toThrow();
    });

    it('should still call onStageChange when stage changes', () => {
      const { rerender } = render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
          statesProcessed={0}
          onStageChange={mockOnStageChange}
        />
      );

      // Rerender with states processed to trigger stage change
      rerender(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
          statesProcessed={2}
          onStageChange={mockOnStageChange}
        />
      );

      expect(mockOnStageChange).toHaveBeenCalled();
    });
  });

  describe('Timeout overlay', () => {
    it('should show timeout overlay when showTimeoutOverlay is true', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
          showTimeoutOverlay={true}
        />
      );

      expect(screen.getByText(/Busca expirou — preparando resultados/)).toBeInTheDocument();
    });
  });

  describe('SSE indicators', () => {
    it('should show reconnecting indicator', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
          isReconnecting={true}
        />
      );

      expect(screen.getByTestId('sse-reconnecting-indicator')).toBeInTheDocument();
      expect(screen.getByText('Reconectando...')).toBeInTheDocument();
    });

    it('should show SSE disconnected indicator', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
          sseDisconnected={true}
        />
      );

      expect(screen.getByTestId('sse-fallback-indicator')).toBeInTheDocument();
      expect(screen.getByText(/Progresso estimado \(conexão em tempo real indisponível\)/)).toBeInTheDocument();
    });

    it('should show real-time indicator when SSE event is present', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
          sseEvent={{ stage: 'fetching', progress: 20, message: '' } as any}
        />
      );

      expect(screen.getByTestId('sse-realtime-indicator')).toBeInTheDocument();
      expect(screen.getByText('Progresso em tempo real')).toBeInTheDocument();
    });
  });

  describe('Progress calculation (internal)', () => {
    it('should cap at connecting stage (10%) when no states processed yet', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={5}
          statesProcessed={0}
        />
      );

      const progressBar = screen.getByRole('progressbar');
      const value = parseInt(progressBar.getAttribute('aria-valuenow') || '0');
      expect(value).toBeLessThanOrEqual(10);
    });

    it('should update aria-valuenow as progress changes', async () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={20}
          stateCount={3}
          statesProcessed={2}
        />
      );

      const progressBar = screen.getByRole('progressbar');
      const valueNow = parseInt(progressBar.getAttribute('aria-valuenow') || '0');
      expect(valueNow).toBeGreaterThan(0);
      expect(valueNow).toBeLessThanOrEqual(100);
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
        />
      );

      const statusElement = screen.getByRole('status');
      expect(statusElement).toHaveAttribute('aria-live', 'polite');
      expect(statusElement).toHaveAttribute('aria-label', 'Analisando oportunidades');
    });

    it('should have progressbar role with correct values', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
        />
      );

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow');
      expect(progressBar).toHaveAttribute('aria-valuemin', '0');
      expect(progressBar).toHaveAttribute('aria-valuemax', '100');
    });

    it('should show degraded aria-label when isDegraded', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
          isDegraded={true}
        />
      );

      const statusElement = screen.getByRole('status');
      expect(statusElement).toHaveAttribute('aria-label', 'Resultados disponíveis com ressalvas');
    });
  });

  describe('Edge cases', () => {
    it('should handle very short estimated time', () => {
      expect(() =>
        render(
          <EnhancedLoadingProgress
            currentStep={1}
            estimatedTime={0.5}
            stateCount={1}
          />
        )
      ).not.toThrow();
    });

    it('should handle stateCount = 0', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={0}
        />
      );

      expect(screen.getByText(/Processando 0 estados/)).toBeInTheDocument();
    });

    it('should handle long-running filter message', () => {
      render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={3}
          sseEvent={{ stage: 'filtering', progress: 65, message: '', detail: { is_long_running: true } } as any}
        />
      );

      expect(screen.getByTestId('long-running-message')).toBeInTheDocument();
      expect(screen.getByText(/Volume grande, pode levar até 2 min/)).toBeInTheDocument();
    });
  });

  describe('Snapshot', () => {
    it('should match visual snapshot of new carousel component', () => {
      const { container } = render(
        <EnhancedLoadingProgress
          currentStep={1}
          estimatedTime={60}
          stateCount={5}
          statesProcessed={2}
          onCancel={mockOnCancel}
        />
      );

      expect(container.firstChild).toMatchSnapshot();
    });
  });
});
