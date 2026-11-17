#!/usr/bin/env python3
"""
Text Input Onboarding - Demo-Level Parser
Converts simple text to structured app data
NO NLP, NO ML - Simple keyword matching only

Example:
    Input: "This is my backend service"
    Output: {
        "app_name": "backend-service",
        "env": "dev",
        "state": "newly_onboarded",
        "runtime_type": "backend"
    }
"""

import re
from typing import Dict, Any
from datetime import datetime


class TextInputOnboarder:
    """
    Demo-level text input onboarding
    
    Simple keyword-based parsing (no NLP/ML)
    Converts free text to structured runtime data
    """
    
    # Simple keyword mapping (demo logic only)
    KEYWORDS = {
        'backend': 'backend',
        'api': 'backend',
        'service': 'backend',
        'server': 'backend',
        'frontend': 'frontend',
        'ui': 'frontend',
        'web': 'frontend',
        'app': 'fullstack',
        'application': 'fullstack'
    }
    
    def parse_text_input(self, text_input: str) -> Dict[str, Any]:
        """
        Parse free text into structured onboarding data
        
        Demo-level logic:
        - Extract keywords
        - Infer runtime type
        - Generate safe app name
        - Default to 'dev' environment
        
        Args:
            text_input: Free text like "This is my backend service"
            
        Returns:
            Structured onboarding event for agent runtime
        """
        
        if not text_input or not text_input.strip():
            raise ValueError("Text input cannot be empty")
        
        # Normalize input
        text_lower = text_input.lower().strip()
        
        # Extract runtime type from keywords
        runtime_type = self._detect_runtime_type(text_lower)
        
        # Generate safe app name from text
        app_name = self._generate_app_name(text_input, runtime_type)
        
        # Build structured event
        onboarding_event = {
            'event_type': 'app_onboarding',
            'event_id': f'onboard-{datetime.now().strftime("%Y%m%d%H%M%S")}',
            'timestamp': datetime.now().isoformat(),
            'app_name': app_name,
            'env': 'dev',  # Always dev for demo onboarding
            'state': 'newly_onboarded',  # Special state to trigger NOOP
            'runtime_type': runtime_type,
            'original_input': text_input[:100],  # Truncate for logging
            'source': 'text_input_onboarding'
        }
        
        return onboarding_event
    
    def _detect_runtime_type(self, text: str) -> str:
        """
        Detect runtime type from keywords
        
        Args:
            text: Normalized text input
            
        Returns:
            Runtime type: 'backend', 'frontend', or 'fullstack'
        """
        words = re.findall(r'\w+', text)
        
        # Check each word against keyword map
        for word in words:
            if word in self.KEYWORDS:
                return self.KEYWORDS[word]
        
        # Default if no keywords found
        return 'backend'
    
    def _generate_app_name(self, text: str, runtime_type: str) -> str:
        """
        Generate safe app name from text
        
        Logic:
        - Extract meaningful words
        - Combine with runtime type
        - Ensure lowercase alphanumeric with hyphens
        
        Args:
            text: Original text input
            runtime_type: Detected runtime type
            
        Returns:
            Safe app name (e.g., 'backend-service')
        """
        # Extract words (alphanumeric only)
        words = re.findall(r'\w+', text.lower())
        
        # Filter out common filler words
        filler_words = {'this', 'is', 'my', 'the', 'a', 'an', 'for', 'to', 'of'}
        meaningful_words = [w for w in words 
                          if w not in filler_words 
                          and len(w) > 2 
                          and w not in self.KEYWORDS]
        
        if meaningful_words:
            # Take first meaningful word
            base_name = meaningful_words[0]
        else:
            # Fallback
            base_name = 'app'
        
        # Combine with runtime type
        app_name = f"{runtime_type}-{base_name}"
        
        # Ensure valid format (lowercase alphanumeric with hyphens)
        app_name = re.sub(r'[^a-z0-9-]', '', app_name)
        app_name = re.sub(r'-+', '-', app_name)  # No double hyphens
        app_name = app_name.strip('-')  # No leading/trailing hyphens
        
        # Truncate to max 50 chars
        return app_name[:50]


def onboard_from_text(text_input: str) -> Dict[str, Any]:
    """
    Quick interface for text input onboarding
    
    Args:
        text_input: Free text input (e.g., "This is my backend service")
        
    Returns:
        Structured onboarding event
        
    Example:
        >>> event = onboard_from_text("This is my backend service")
        >>> print(event['app_name'])
        'backend-service'
        >>> print(event['state'])
        'newly_onboarded'
    """
    onboarder = TextInputOnboarder()
    return onboarder.parse_text_input(text_input)


if __name__ == "__main__":
    # Demo/test usage
    examples = [
        "This is my backend service",
        "my frontend ui",
        "api server",
        "web application"
    ]
    
    print("="*60)
    print("TEXT INPUT ONBOARDING - DEMO")
    print("="*60)
    
    for text in examples:
        print(f"\nInput: \"{text}\"")
        result = onboard_from_text(text)
        print(f"  App Name: {result['app_name']}")
        print(f"  Runtime Type: {result['runtime_type']}")  
        print(f"  Env: {result['env']}")
        print(f"  State: {result['state']}")
