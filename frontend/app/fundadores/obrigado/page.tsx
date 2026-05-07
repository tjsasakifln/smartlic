import type { Metadata } from 'next';
import { FundadoresObrigadoClient } from './FundadoresObrigadoClient';

export const metadata: Metadata = {
  title: 'Bem-vindo ao Plano Fundadores | SmartLic',
  description: 'Seu acesso vitalício ao SmartLic está sendo ativado.',
  robots: { index: false, follow: false },
};

export default function FundadoresObrigadoPage() {
  return <FundadoresObrigadoClient />;
}
