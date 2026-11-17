import os
import csv
import datetime

class FeedbackHandler:
    """Handles user feedback collection and logging."""
    
    def __init__(self, log_file=None):
        self.log_file = log_file or os.path.join("logs", r"user_feedback_log.csv")
    
    def get_feedback(self, state, action, outcome):
        """Get user feedback for an action."""
        return get_user_feedback_from_terminal(state, action, outcome)
    
    def log_feedback(self, state, action, outcome, feedback):
        """Log user feedback."""
        log_user_feedback(self.log_file, state, action, outcome, feedback)

def get_user_feedback_from_terminal(state, action, outcome):
    """
    Prompts the user for feedback directly in the terminal.
    
    Args:
        state (str): The failure state detected (e.g., 'deployment_failure_DOWN').
        action (str): The action the agent chose (e.g., 'retry_deployment').
        outcome (str): The result of the action ('success' or 'failure').
        
    Returns:
        str: 'accepted' or 'rejected' based on user input.
    """
    print("\n" + "="*30)
    print("✍️ USER FEEDBACK REQUIRED:")
    print(f"  - Problem Detected: {state}")
    print(f"  - Agent's Chosen Action: {action}")
    print(f"  - System Outcome: {outcome}")
    
    for _ in range(3):
        response = input("Do you accept this action as a good solution for this problem? (y/n): ").lower().strip()
        if response in ['y', 'yes']:
            print(" -> Feedback recorded: ACCEPTED.")
            return 'accepted'
        elif response in ['n', 'no']:
            print(" -> Feedback recorded: REJECTED.")
            return 'rejected'
        else:
            print("Invalid input. Please enter 'y' for yes or 'n' for no.")
    print(" -> Max attempts reached. Recording REJECTED by default.")
    return 'rejected'

def log_user_feedback(log_file, state, action, outcome, feedback):
    """
    Logs the user's raw feedback to a permanent history file.
    
    Args:
        log_file (str): Path to the feedback log (e.g., 'logs/user_feedback_log.csv').
        state (str): The failure state.
        action (str): The action taken.
        outcome (str): The system's outcome ('success' or 'failure').
        feedback (str): The user's feedback ('accepted' or 'rejected').
    """
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    header = ["timestamp", "state", "action", "system_outcome", "user_feedback"]
    
    file_exists = os.path.exists(log_file)
    
    timestamp = datetime.datetime.now().isoformat()
    with open(log_file, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists or f.tell() == 0:
            writer.writerow(header)
        writer.writerow([timestamp, state, action, outcome, feedback])
    print(f" -> User feedback permanently stored in {log_file}")

