#!/usr/bin/env python3
"""
RL Remote Client
Handles HTTP communication with the remote RL decision service.
"""

import requests
import json
import time
import logging
from typing import Dict, Any, Optional

class RLRemoteClient:
    """Client for the remote RL Decision Brain service."""
    
    DEFAULT_URL = "https://rl-autonomous-decision-brain-py-3.onrender.com/decide"
    
    def __init__(self, url: Optional[str] = None, timeout: float = 2.0):
        self.url = url or self.DEFAULT_URL
        self.timeout = timeout
        self.logger = logging.getLogger("RLRemoteClient")
        
        # Simple circuit breaker state
        self._consecutive_failures = 0
        self._last_failure_time = 0
        self._cooldown_period = 300 # 5 minutes
        self._max_failures = 3

    def decide(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send state to remote RL service and get decision.
        
        Args:
            state_dict: The adapted state following RL schema
            
        Returns:
            RL decision dictionary or fallback
        """
        # 1. Check Circuit Breaker
        if self._consecutive_failures >= self._max_failures:
            if time.time() - self._last_failure_time < self._cooldown_period:
                self.logger.warning("RL Remote Client: Circuit breaker active. Skipping remote call.")
                return self._fallback_response("Circuit breaker active (RL Service Unavailable)")
            else:
                # Reset after cooldown
                self._consecutive_failures = 0

        # 2. Prepare Request
        try:
            headers = {'Content-Type': 'application/json'}
            
            # Use /decide endpoint if not already in URL
            request_url = self.url
            if not request_url.endswith('/decide'):
                request_url = request_url.rstrip('/') + '/decide'

            self.logger.info(f"RL Remote Client: Calling {request_url}")
            
            response = requests.post(
                request_url,
                json=state_dict,
                headers=headers,
                timeout=self.timeout
            )
            
            # 3. Handle Response
            if response.status_code == 200:
                self._consecutive_failures = 0
                return response.json()
            else:
                self._track_failure()
                self.logger.error(f"RL Remote Client: Remote service returned error {response.status_code}")
                return self._fallback_response(f"HTTP Error {response.status_code}")

        except requests.exceptions.Timeout:
            self._track_failure()
            self.logger.error("RL Remote Client: Request timed out (2s threshold)")
            return self._fallback_response("Request timed out")
        except requests.exceptions.RequestException as e:
            self._track_failure()
            self.logger.error(f"RL Remote Client: Connection error: {str(e)}")
            return self._fallback_response(f"Connection error: {str(e)}")
        except Exception as e:
            self._track_failure()
            self.logger.error(f"RL Remote Client: Unexpected error: {str(e)}")
            return self._fallback_response(f"Unexpected error: {str(e)}")

    def get_scope(self) -> Dict[str, Any]:
        """Fetch the allowed action scope from remote service."""
        try:
            request_url = self.url.replace('/decide', '/scope')
            response = requests.get(request_url, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            return {"error": f"HTTP {response.status_code}", "scope": {}}
        except Exception as e:
            return {"error": str(e), "scope": {}}

    def get_health(self) -> Dict[str, Any]:
        """Check health of the remote RL service."""
        try:
            request_url = self.url.replace('/decide', '/health')
            response = requests.get(request_url, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            return {"status": "error", "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def send_execution_feedback(self, feedback_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send execution success/failure feedback back to RL service.
        Best-effort: does not affect main runtime flow on network/API errors.
        """
        try:
            feedback_url = self.url
            if feedback_url.endswith('/decide'):
                feedback_url = feedback_url[:-len('/decide')] + '/feedback'
            else:
                feedback_url = feedback_url.rstrip('/') + '/feedback'

            response = requests.post(
                feedback_url,
                json=feedback_payload,
                headers={'Content-Type': 'application/json'},
                timeout=min(self.timeout, 2.0)
            )

            if response.status_code in (200, 201, 202):
                body = {}
                try:
                    body = response.json()
                except ValueError:
                    body = {'message': response.text[:200]}
                return {
                    'delivered': True,
                    'status_code': response.status_code,
                    'response': body
                }

            return {
                'delivered': False,
                'status_code': response.status_code,
                'reason': f'feedback endpoint returned HTTP {response.status_code}'
            }
        except Exception as e:
            return {
                'delivered': False,
                'reason': str(e)
            }

    def _track_failure(self):
        self._consecutive_failures += 1
        self._last_failure_time = time.time()

    def _fallback_response(self, reason: str) -> Dict[str, Any]:
        """Return a safe NOOP fallback when remote RL fails."""
        return {
            "action": "noop",
            "confidence": 0.0,
            "reason": f"Fallback: {reason}",
            "source": "remote_client_fallback"
        }
