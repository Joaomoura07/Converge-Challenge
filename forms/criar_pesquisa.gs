/**
 * Cria o Google Forms "Pesquisa Rápida: Automação em Arquitetura".
 * Uso: script.google.com -> Novo projeto -> cole este código -> Executar (criarForm).
 * Depois abra Execuções/Registros para ver o link de edição e o link público.
 */
function criarForm() {
  var form = FormApp.create('Pesquisa Rápida: Automação em Arquitetura (Projeto de Hackathon)');
  form.setDescription(
    'Olá! Somos uma equipe competindo no hackathon Converge Challenge. ' +
    'Estamos criando uma Inteligência Artificial para automatizar os orçamentos e estudos de viabilidade. ' +
    'Sua resposta rápida (menos de 1 minuto) vai nos ajudar a validar nosso projeto com os jurados!'
  );

  function radio(titulo, opcoes) {
    form.addMultipleChoiceItem().setTitle(titulo).setRequired(true).setChoiceValues(opcoes);
  }

  radio('1. Qual o seu momento profissional atual?', [
    'Estudante de Arquitetura / Estagiário',
    'Arquiteto(a) Autônomo(a)',
    'Dono(a) / Sócio(a) de Escritório',
    'Outro'
  ]);

  radio('2. Hoje, quanto tempo você (ou seu escritório) gasta em média para montar o orçamento base / estudo de viabilidade de um projeto?', [
    'Ainda não atuo na área / Não faço orçamentos',
    'Menos de 2 horas',
    'Entre 2h e 5 horas',
    'Entre 1 e 2 dias inteiros de trabalho',
    'Mais de 3 dias esperando lojistas responderem'
  ]);

  form.addCheckboxItem()
    .setTitle('3. De acordo com a sua experiência, qual é a parte mais frustrante desse processo de orçamentação? (Múltipla escolha)')
    .setRequired(true)
    .setChoiceValues([
      'Ficar planilhando e separando itens manualmente.',
      'A demora das lojas físicas para devolverem as cotações.',
      'A dificuldade de achar preços de referência na internet para ter um "balizador".',
      'Descobrir depois de pronto que o projeto estourou o orçamento do cliente.'
    ]);

  radio('4. Imagine um sistema onde você faz upload da lista do SketchUp/Revit, e a IA devolve em 3 minutos o preço médio de internet de cada item e a divisão logística (onde comprar). Qual seria o impacto disso na sua rotina?', [
    'Revolucionário. Mudaria completamente meu fluxo de trabalho.',
    'Muito útil. Economizaria boas horas na semana.',
    'Legal, mas não mudaria tanto a minha vida.',
    'Não usaria.'
  ]);

  radio('5. Sobre os itens sem especificação (ex: você exportou apenas "cadeira"), como você prefere que o sistema aja?', [
    'Me alerte que está genérico para eu preencher a marca/modelo antes de orçar.',
    'Chute um preço médio com base no padrão do projeto (Alto ou Econômico).'
  ]);

  radio('6. Se essa ferramenta entregasse o que promete, qual modelo de cobrança faria mais sentido para você ou seu escritório?', [
    'Assinatura mensal fixa para projetos ilimitados.',
    'Pagamento avulso por projeto processado (taxa por lista exportada).',
    'Se fosse pago, eu não compraria.'
  ]);

  Logger.log('Editar: ' + form.getEditUrl());
  Logger.log('Responder (link público): ' + form.getPublishedUrl());
}
