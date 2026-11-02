"""
Lancador das funcionalidades de hand tracking.

    python main.py                 -> lista os comandos
    python main.py <comando> [...] -> roda a funcionalidade (args extras sao repassados)

Para adicionar uma funcionalidade nova: crie apps/<nome>.py com uma funcao
main(argv) e registre aqui em COMMANDS.
"""
import importlib
import runpy
import sys

# comando -> (modulo, descricao)
COMMANDS = {
    "gestos": ("apps.gesture_game", "Jogo: imite o gesto de mao que aparece na tela"),
    "corte":  ("apps.slice_game",  "Jogo: corte as frutas no ar com o indicador (1 ou 2 jogadores)"),
    "teremim": ("apps.theremin",    "Simulador de teremim: mao direita = nota, esquerda = volume"),
    "circulo": ("apps.color_wheel", "Circulo cromatico: toque nas notas coloridas para tocar"),
    "mouse":  ("hand_tracking",     "Controla o mouse com o indicador (script original)"),
}


def usage() -> None:
    print("Uso: python main.py <comando> [opcoes]\n\nComandos disponiveis:")
    for name, (_, desc) in COMMANDS.items():
        print(f"  {name:<10} {desc}")
    print("\nAjuda de um comando: python main.py <comando> --help")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        usage()
        return
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd not in COMMANDS:
        print(f"Comando desconhecido: {cmd}\n")
        usage()
        sys.exit(1)

    module_name = COMMANDS[cmd][0]
    module = importlib.import_module(module_name) if module_name.startswith("apps.") else None
    if module is not None and hasattr(module, "main"):
        module.main(rest)
    else:
        # scripts antigos que rodam direto no nivel do modulo
        sys.argv = [module_name] + rest
        runpy.run_module(module_name, run_name="__main__")


if __name__ == "__main__":
    main()
