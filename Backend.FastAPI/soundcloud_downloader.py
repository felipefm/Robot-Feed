
import argparse
import yt_dlp
import sys
import os

def download_soundcloud_track(url, browser=None, proxy=None):
    """
    Downloads a track from a given SoundCloud URL as an MP3 file.
    """
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': '%(title)s.%(ext)s',
        'noplaylist': True,
        'overwrites': True, # Força o download mesmo que o arquivo já exista
    }

    if browser:
        print(f"Usando cookies do navegador: {browser}")
        ydl_opts['cookiesfrombrowser'] = (browser,)
    
    if proxy:
        print(f"Usando o proxy: {proxy}")
        ydl_opts['proxy'] = proxy

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Baixando e convertendo: {url}")
            ydl.download([url])
            print("Download concluído com sucesso!")
    except Exception as e:
        print(f"Ocorreu um erro: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Baixa uma música do SoundCloud em formato MP3.")
    parser.add_argument("url", help="O URL da música no SoundCloud.")
    parser.add_argument(
        "--browser",
        help="Navegador para usar cookies (ex: chrome, firefox, opera, edge). Requer estar logado no SoundCloud no navegador.",
        default=None
    )
    parser.add_argument(
        "--proxy",
        help="URL do proxy a ser usado (ex: socks5://127.0.0.1:9050)",
        default=None
    )

    args = parser.parse_args()

    if not args.url:
        print("Erro: Você precisa fornecer um URL.", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    download_soundcloud_track(args.url, args.browser, args.proxy)
