import threading
import bots.quiz as quiz
import bots.registrator as registrator
import logging
import time

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

def run_registrator():
    registrator.main()  # Assuming main() accepts this parameter

def run_quiz():
    quiz.main()  # Assuming main() accepts this parameter

def main():
    # Create threads for each bot
    registrator_thread = threading.Thread(target=run_registrator, name="RegistratorBot")
    quiz_thread = threading.Thread(target=run_quiz, name="QuizBot")
    
    # Start both bots
    registrator_thread.start()
    quiz_thread.start()
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)  # Sleep to prevent high CPU usage
    except KeyboardInterrupt:
        logging.info("Received shutdown signal")

if __name__ == "__main__":
    main()