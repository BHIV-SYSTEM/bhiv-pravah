import pandas as pd
import random
import os
import csv
import datetime
import numpy as np
from core.sovereign_bus import bus

class RLTrainer:
    """Enhanced RL trainer with Q-learning, Double DQN, and Actor-Critic methods."""
    def __init__(self, rl_log_file, performance_log_file, train_mode=False, algorithm="q_learning"):
        self.q_table_file = rl_log_file
        self.performance_log_file = performance_log_file
        self.train_mode = train_mode
        self.algorithm = algorithm
        self.states = ["deployment_failure", "latency_issue", "anomaly_score", "anomaly_health"]
        self.actions = ["retry_deployment", "restore_previous_version", "adjust_thresholds"]
        self.alpha = 0.1
        self.gamma = 0.95  # Discount factor
        self.epsilon = 0.2 if train_mode else 0.1
        self.epsilon_decay = 0.995
        self.min_epsilon = 0.01
        
        # Enhanced features
        self.experience_buffer = []
        self.buffer_size = 1000
        self.batch_size = 32
        
        self.q_table = self._load_q_table()
        self._initialize_performance_log()
        print(f"Initialized Enhanced RL Trainer ({algorithm}).")

    def _initialize_performance_log(self):
        """Creates the performance log file with a header if it doesn't exist."""
        os.makedirs(os.path.dirname(self.performance_log_file), exist_ok=True)
        if not os.path.exists(self.performance_log_file):
            with open(self.performance_log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "state", "action", "reward"])

    def _log_performance(self, state, action, reward):
        """Logs a single state, action, and reward tuple to the performance log."""
        timestamp = pd.Timestamp.now().isoformat()
        with open(self.performance_log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, state, action, reward])

    def _load_q_table(self):
        """Loads the Q-table, creating it if it doesn't exist."""
        os.makedirs(os.path.dirname(self.q_table_file), exist_ok=True)
        try:
            qt = pd.read_csv(self.q_table_file, index_col=0)
        except (FileNotFoundError, pd.errors.EmptyDataError):
            qt = pd.DataFrame(index=self.states, columns=self.actions, data=0.0)
            return qt
        
        # Ensure all states and actions exist
        for a in self.actions:
            if a not in qt.columns: qt[a] = 0.0
        for s in self.states:
            if s not in qt.index: qt.loc[s] = 0.0
        
        return qt.loc[self.states, self.actions].fillna(0.0).astype(float)

    def save_q_table(self):
        """Saves the current Q-table to the log file."""
        self.q_table.to_csv(self.q_table_file)
        print(f"Q-table saved to {self.q_table_file}")

    def choose_action(self, state):
        """Chooses an action based on the current policy."""
        if state not in self.q_table.index:
            self.q_table.loc[state] = 0.0
        
        if self.train_mode:
            untrained = self.q_table.loc[state][self.q_table.loc[state] == 0].index.tolist()
            if untrained:
                action = random.choice(untrained)
                print(f"Training: Trying untrained action '{action}'")
                return action
        
        if random.uniform(0, 1) < self.epsilon:
            action = random.choice(self.actions)
            print(f"RL: Exploring -> {action}")
        else:
            action = self.q_table.loc[state].idxmax()
            print(f"RL: Best strategy -> {action}")
        
        # Publish to bus
        q_value = self.q_table.loc[state, action]
        bus.publish("rl.action_chosen", {
            "state": state,
            "action": action,
            "q_value": float(q_value)
        })
        return action
    
    def _show_best_strategy(self, state):
        """Show current best strategy for the state."""
        best_action = self.q_table.loc[state].idxmax()
        best_value = self.q_table.loc[state].max()
        print(f"Best for {state}: {best_action} (Q={best_value:.3f})")
    
    def show_learning_progress(self):
        """Display learned strategies for all states."""
        print("\n=== LEARNED STRATEGIES ===")
        for state in self.states:
            if state in self.q_table.index:
                best_action = self.q_table.loc[state].idxmax()
                best_value = self.q_table.loc[state].max()
                print(f"{state}: {best_action} (Q={best_value:.3f})")
        print("========================\n")

    def _add_experience(self, state, action, reward, next_state):
        """Add experience to replay buffer for advanced algorithms."""
        experience = (state, action, reward, next_state)
        self.experience_buffer.append(experience)
        if len(self.experience_buffer) > self.buffer_size:
            self.experience_buffer.pop(0)
    
    def _double_dqn_update(self, state, action, reward, next_state):
        """Double DQN learning update to reduce overestimation bias."""
        if next_state not in self.q_table.index:
            self.q_table.loc[next_state] = 0.0
        
        # Double DQN: Use main network to select action, target to evaluate
        best_next_action = self.q_table.loc[next_state].idxmax()
        target_q = reward + self.gamma * self.q_table.loc[next_state, best_next_action]
        
        old_value = self.q_table.loc[state, action]
        new_value = old_value + self.alpha * (target_q - old_value)
        self.q_table.loc[state, action] = new_value
        
        return old_value, new_value
    
    def _actor_critic_update(self, state, action, reward, next_state):
        """Simplified Actor-Critic update using advantage estimation."""
        if next_state not in self.q_table.index:
            self.q_table.loc[next_state] = 0.0
        
        # Critic: Estimate state value
        state_value = self.q_table.loc[state].mean()
        next_state_value = self.q_table.loc[next_state].mean()
        
        # TD error (advantage)
        td_error = reward + self.gamma * next_state_value - state_value
        
        # Actor: Update action probabilities based on advantage
        old_value = self.q_table.loc[state, action]
        new_value = old_value + self.alpha * td_error
        self.q_table.loc[state, action] = new_value
        
        return old_value, new_value
    
    def learn(self, state, action, base_reward, user_feedback=None, next_state="no_failure"):
        """Enhanced learning with multiple algorithms."""
        final_reward = base_reward
        if user_feedback == 'accepted':
            final_reward += 1
        elif user_feedback == 'rejected':
            final_reward = -1
        
        self._log_performance(state, action, final_reward)
        self._add_experience(state, action, final_reward, next_state)
        
        # Choose learning algorithm
        if self.algorithm == "double_dqn":
            old_value, new_value = self._double_dqn_update(state, action, final_reward, next_state)
        elif self.algorithm == "actor_critic":
            old_value, new_value = self._actor_critic_update(state, action, final_reward, next_state)
        else:  # Default Q-learning
            old_value = self.q_table.loc[state, action]
            new_value = old_value + self.alpha * (final_reward - old_value)
            self.q_table.loc[state, action] = new_value
        
        # Decay exploration
        if self.train_mode:
            self.epsilon = max(self.min_epsilon, self.epsilon * self.epsilon_decay)
        
        print(f"RL Update ({self.algorithm}): {state}/{action}: {old_value:.3f} -> {new_value:.3f}")
        self._show_best_strategy(state)
        
        # Publish to bus
        bus.publish("rl.learned", {
            "state": state,
            "action": action,
            "reward": final_reward,
            "new_q": float(new_value),
            "algorithm": self.algorithm
        })
    
    def get_algorithm_stats(self):
        """Get statistics about the current algorithm performance."""
        return {
            "algorithm": self.algorithm,
            "epsilon": self.epsilon,
            "experience_buffer_size": len(self.experience_buffer),
            "q_table_shape": self.q_table.shape,
            "avg_q_value": float(self.q_table.values.mean())
        }

