from agent import Agent
import ui


def main():
    ui.print_welcome()
    agent = Agent(verbose=True, enable_logging=True)

    while True:
        try:
            user_input = ui.prompt_user()
        except (KeyboardInterrupt, EOFError):
            ui.console.print()
            _farewell(agent)
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        if cmd in ("/quit", "/exit", "quit", "exit"):
            _farewell(agent)
            break

        if cmd == "/reset":
            agent.reset()
            ui.success("Conversation reset (new session started).")
            continue

        if cmd == "/stats":
            ui.print_stats(agent.get_stats())
            continue

        if cmd == "/logs":
            if agent.logger:
                ui.info(f"Log file: {agent.logger.get_log_path()}")
            else:
                ui.warning("Logging is disabled")
            continue

        try:
            answer = agent.chat(user_input)
            ui.print_assistant_answer(answer)
        except KeyboardInterrupt:
            ui.warning("Cancelled by user")
        except Exception as e:
            ui.error(f"{type(e).__name__}: {e}")
            ui.dim("Try again or type /reset to start over.")


def _farewell(agent: Agent):
    ui.console.print()
    ui.info("Goodbye!")
    ui.print_stats(agent.get_stats())


if __name__ == "__main__":
    main()
