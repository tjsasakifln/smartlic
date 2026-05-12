export default function FundadoresLegalFooter() {
  return (
    <footer className="mt-12 border-t border-slate-200 pt-6 text-sm text-slate-500">
      <p>
        Ao prosseguir, você concorda com os{' '}
        <a href="/termos/fundadores" className="text-blue-600 underline">
          Termos do Plano Fundadores
        </a>{' '}
        e a{' '}
        <a href="/privacidade" className="text-blue-600 underline">
          Política de Privacidade
        </a>
        . Em caso de dúvida, escreva para{' '}
        <a href="mailto:tiago.sasaki@confenge.com.br" className="text-blue-600 underline">
          tiago.sasaki@confenge.com.br
        </a>
        .
      </p>
    </footer>
  );
}
