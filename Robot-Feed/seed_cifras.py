"""
seed_cifras.py - Popular a tabela 'musica' com dados de teste (uso manual).

NÃO é chamado automaticamente em lugar nenhum. Rodar uma única vez à mão,
dentro do container, depois que a tabela 'musica' já tiver sido criada pela
migração (inspect_and_migrate) no start do app:

    docker compose exec <servico> python seed_cifras.py

As duas músicas abaixo são fictícias (placeholder), sem nenhuma letra real.
"""

from app import app
from routes.cifras import salvar_musica


MUSICAS_EXEMPLO = [
    {
        'slug': 'exemplo-um',
        'titulo': 'Música de Exemplo Um',
        'artista': 'Artista Fictício',
        'tom_original': 'G',
        'capotraste': 0,
        'blocos': [
            {'acordes': 'G           C', 'letra': 'Esta é uma letra fictícia de teste'},
            {'acordes': 'D           Em', 'letra': 'Só para preencher a tela por enquanto'},
            {'acordes': 'C           G', 'letra': 'Nenhuma música real foi utilizada aqui'},
            {'acordes': 'D           G', 'letra': 'Troque depois pelo carregamento real'},
        ],
    },
    {
        'slug': 'exemplo-dois',
        'titulo': 'Música de Exemplo Dois',
        'artista': 'Banda Fictícia',
        'tom_original': 'Am',
        'capotraste': 2,
        'blocos': [
            {'acordes': 'Am          F', 'letra': 'Linha de exemplo número um'},
            {'acordes': 'C           G', 'letra': 'Linha de exemplo número dois'},
            {'acordes': 'Am          F', 'letra': 'Conteúdo meramente ilustrativo'},
            {'acordes': 'C     G     Am', 'letra': 'Fim do trecho de demonstração'},
        ],
    },
]


def main():
    with app.app_context():
        for m in MUSICAS_EXEMPLO:
            salvar_musica(
                m['slug'],
                m['titulo'],
                m['artista'],
                m['tom_original'],
                m['blocos'],
                capotraste=m['capotraste'],
            )
            print(f"✅ Música salva: {m['slug']} ({m['titulo']})")

    print(f"✅ Seed concluído: {len(MUSICAS_EXEMPLO)} músicas de teste inseridas/atualizadas.")


if __name__ == '__main__':
    main()
