#!/usr/bin/env python3
"""
Selection Autocomplete with Fast Key Combinations
- Configurable timeout for key combinations
- Fast detection and invalidation
- Complete configuration system
- Anti-stuck mechanisms
"""

import requests
import json
import time
import threading
import logging
import os
import configparser
from datetime import datetime
from pynput import keyboard
from pynput.keyboard import Key, Listener
import subprocess
import pyperclip
import re
import signal
import sys
import tkinter as tk
from tkinter import ttk

class CompletionPopup:
    def __init__(self, options, callback, config):
        self.callback = callback
        self.selected_option = None
        self.config = config
        
        # Create popup window
        self.root = tk.Tk()
        self.root.title("🤖 AI Completion Options")
        
        # Get window size from config
        width = self.config.getint('popup', 'window_width', fallback=850)
        height = self.config.getint('popup', 'window_height', fallback=500)
        self.root.geometry(f"{width}x{height}")
        self.root.resizable(True, True)
        
        # Make window stay on top and focused
        self.root.attributes('-topmost', True)
        self.root.focus_force()
        
        # Center the window
        self.center_window()
        
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="🤖 Select AI Completion:", font=("Arial", 12, "bold"))
        title_label.grid(row=0, column=0, pady=(0, 10), sticky=tk.W)
        
        # Create scrollable frame for options
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Grid the canvas and scrollbar
        canvas.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
        
        # Configure canvas weight
        main_frame.rowconfigure(1, weight=1)
        
        # Add options as clickable buttons
        self.option_buttons = []
        max_preview = self.config.getint('popup', 'max_preview_length', fallback=150)
        show_numbers = self.config.getboolean('popup', 'show_option_numbers', fallback=True)
        
        for i, option in enumerate(options):
            # Create a frame for each option
            option_frame = ttk.Frame(scrollable_frame, relief="groove", padding="10")
            option_frame.grid(row=i, column=0, sticky=(tk.W, tk.E), pady=3)
            scrollable_frame.columnconfigure(0, weight=1)
            
            # Option text with optional numbering
            preview_text = option[:max_preview] + "..." if len(option) > max_preview else option
            
            if show_numbers:
                button_text = f"[{i+1}] {preview_text}"
            else:
                button_text = preview_text
            
            option_button = tk.Button(
                option_frame,
                text=button_text,
                wraplength=width-120,
                justify=tk.LEFT,
                anchor="w",
                font=("Arial", 10),
                bg="#f8f8f8",
                relief="raised",
                padx=10,
                pady=8,
                command=lambda opt=option: self.select_option(opt)
            )
            option_button.pack(fill=tk.X)
            
            # Hover effects
            def on_enter(e, btn=option_button):
                btn.config(bg="#e8e8e8")
            
            def on_leave(e, btn=option_button):
                btn.config(bg="#f8f8f8")
            
            option_button.bind("<Enter>", on_enter)
            option_button.bind("<Leave>", on_leave)
            
            self.option_buttons.append(option_button)
        
        # Bottom frame for buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, pady=(10, 0), sticky=(tk.W, tk.E))
        
        # Cancel button
        cancel_button = ttk.Button(button_frame, text="❌ Cancel", command=self.cancel)
        cancel_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Instructions
        instruction_text = "Click option or press 1-5 for quick selection, Enter for first, Escape to cancel"
        instruction_label = ttk.Label(button_frame, text=instruction_text, font=("Arial", 9))
        instruction_label.pack(side=tk.LEFT)
        
        # Keyboard bindings
        self.root.bind('<Escape>', lambda e: self.cancel())
        self.root.bind('<Return>', lambda e: self.select_first_option())
        
        # Bind number keys for quick selection
        for i in range(1, min(10, len(options) + 1)):
            self.root.bind(str(i), lambda e, idx=i-1: self.select_option(options[idx]))
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.cancel)
    
    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def select_option(self, option):
        """Select an option and close popup"""
        self.selected_option = option
        self.root.quit()
        self.root.destroy()
        if self.callback:
            self.callback(option)
    
    def select_first_option(self):
        """Select first option with Enter key"""
        if self.option_buttons:
            first_text = self.option_buttons[0]['text']
            if first_text.startswith('['):
                actual_text = re.sub(r'^\[\d+\]\s*', '', first_text)
            else:
                actual_text = first_text
            self.select_option(actual_text)
    
    def cancel(self):
        """Cancel selection and close popup"""
        self.selected_option = None
        self.root.quit()
        self.root.destroy()
        if self.callback:
            self.callback(None)
    
    def show(self):
        """Show the popup and wait for selection"""
        self.root.mainloop()
        return self.selected_option


class FastKeyTracker:
    """Fast key combination tracker with configurable timeout"""
    
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        
        # Load timing settings from config
        self.combination_timeout = config.getfloat('timing', 'combination_timeout', fallback=0.8)
        self.max_key_hold_time = config.getfloat('timing', 'max_key_hold_time', fallback=2.0)
        self.cleanup_interval = config.getfloat('timing', 'cleanup_interval', fallback=0.5)
        
        # Debug settings
        self.debug_keys = config.getboolean('debug', 'key_tracking', fallback=False)
        self.debug_timing = config.getboolean('debug', 'show_timing', fallback=False)
        self.log_combinations = config.getboolean('debug', 'log_combinations', fallback=True)
        
        # Key state tracking
        self.key_states = {}  # key -> press_time
        self.combinations = {}  # name -> frozenset of keys
        self.combination_start_time = None
        self.last_activity = time.time()
        
        # Statistics
        self.stats = {
            'total_key_presses': 0,
            'combinations_detected': 0,
            'combinations_timeout': 0,
            'stuck_keys_cleaned': 0
        }
        
        self.start_monitoring()
        
        if self.debug_keys:
            self.logger.info(f"🔧 Fast key tracker initialized (timeout: {self.combination_timeout}s)")
    
    def add_combination(self, name, keys):
        """Add key combination with validation"""
        key_set = frozenset(keys)
        
        # Validate combination
        if len(key_set) == 0:
            self.logger.error(f"❌ Empty combination for '{name}'")
            return False
        
        # Block single modifier keys
        modifier_keys = {Key.ctrl, Key.shift, Key.alt}
        if len(key_set) == 1 and key_set.issubset(modifier_keys):
            self.logger.error(f"❌ Single modifier not allowed for '{name}': {[self.key_to_string(k) for k in keys]}")
            return False
        
        self.combinations[name] = key_set
        
        if self.log_combinations:
            key_names = [self.key_to_string(k) for k in keys]
            self.logger.info(f"✅ Added combination '{name}': {key_names} (timeout: {self.combination_timeout}s)")
        
        return True
    
    def key_to_string(self, key):
        """Convert key to readable string"""
        if hasattr(key, 'name'):
            return key.name
        elif hasattr(key, 'char'):
            return f"'{key.char}'"
        else:
            return str(key)
    
    def on_key_press(self, key):
        """Handle key press with fast timeout logic"""
        current_time = time.time()
        self.stats['total_key_presses'] += 1
        
        # Clean up stuck keys before processing
        self.cleanup_stuck_keys()
        
        # If this is the first key in a potential combination
        if not self.key_states:
            self.combination_start_time = current_time
            if self.debug_timing:
                self.logger.debug(f"⏱️ Starting combination timer: {self.key_to_string(key)}")
        
        # Check if combination has timed out
        elif self.combination_start_time and (current_time - self.combination_start_time) > self.combination_timeout:
            if self.debug_timing:
                elapsed = current_time - self.combination_start_time
                self.logger.debug(f"⏰ Combination timeout ({elapsed:.2f}s > {self.combination_timeout}s) - resetting")
            
            self.stats['combinations_timeout'] += 1
            self.key_states.clear()
            self.combination_start_time = current_time
        
        # Add key to current state
        self.key_states[key] = current_time
        self.last_activity = current_time
        
        if self.debug_keys:
            key_str = self.key_to_string(key)
            active_keys = [self.key_to_string(k) for k in self.key_states.keys()]
            if self.debug_timing and self.combination_start_time:
                elapsed = current_time - self.combination_start_time
                self.logger.debug(f"🔽 {key_str} | Active: {active_keys} | Elapsed: {elapsed:.2f}s")
            else:
                self.logger.debug(f"🔽 {key_str} | Active: {active_keys}")
        
        # Check for complete combinations immediately
        return self.check_combinations()
    
    def on_key_release(self, key):
        """Handle key release"""
        if key in self.key_states:
            del self.key_states[key]
            self.last_activity = time.time()
            
            # If all keys released, reset combination timer
            if not self.key_states:
                self.combination_start_time = None
                if self.debug_timing:
                    self.logger.debug("⏹️ All keys released - timer reset")
            
            if self.debug_keys:
                key_str = self.key_to_string(key)
                active_keys = [self.key_to_string(k) for k in self.key_states.keys()]
                self.logger.debug(f"🔼 {key_str} | Active: {active_keys}")
    
    def check_combinations(self):
        """Check for exact combination matches"""
        current_keys = frozenset(self.key_states.keys())
        
        # Don't match empty set
        if not current_keys:
            return None
        
        # Check each combination for EXACT match
        for name, combo_keys in self.combinations.items():
            if current_keys == combo_keys:
                self.stats['combinations_detected'] += 1
                
                if self.log_combinations:
                    combo_names = [self.key_to_string(k) for k in combo_keys]
                    if self.debug_timing and self.combination_start_time:
                        elapsed = time.time() - self.combination_start_time
                        self.logger.info(f"🎯 MATCH '{name}': {combo_names} (in {elapsed:.2f}s)")
                    else:
                        self.logger.info(f"🎯 MATCH '{name}': {combo_names}")
                
                # Reset state after successful match
                self.key_states.clear()
                self.combination_start_time = None
                
                return name
        
        # Debug: Show partial matches
        if self.debug_keys and current_keys:
            current_names = [self.key_to_string(k) for k in current_keys]
            self.logger.debug(f"🔍 No exact match for: {current_names}")
            
            for name, combo_keys in self.combinations.items():
                if current_keys.issubset(combo_keys):
                    missing = combo_keys - current_keys
                    missing_names = [self.key_to_string(k) for k in missing]
                    self.logger.debug(f"   '{name}' needs: {missing_names}")
        
        return None
    
    def cleanup_stuck_keys(self):
        """Clean up keys held too long"""
        current_time = time.time()
        stuck_keys = []
        
        for key, press_time in list(self.key_states.items()):
            if current_time - press_time > self.max_key_hold_time:
                stuck_keys.append(key)
        
        if stuck_keys:
            self.stats['stuck_keys_cleaned'] += len(stuck_keys)
            
            if self.debug_keys:
                stuck_names = [self.key_to_string(k) for k in stuck_keys]
                self.logger.warning(f"🧹 Cleaning stuck keys: {stuck_names}")
            
            for key in stuck_keys:
                del self.key_states[key]
            
            # Reset combination timer if keys were stuck
            if not self.key_states:
                self.combination_start_time = None
    
    def force_reset(self):
        """Force reset all states"""
        if self.key_states:
            if self.debug_keys:
                active_names = [self.key_to_string(k) for k in self.key_states.keys()]
                self.logger.warning(f"🔄 Force reset: {active_names}")
            
            self.key_states.clear()
        
        self.combination_start_time = None
        self.last_activity = time.time()
    
    def get_stats(self):
        """Get tracker statistics"""
        return self.stats.copy()
    
    def start_monitoring(self):
        """Start background monitoring"""
        def monitor():
            try:
                current_time = time.time()
                
                # Clean up stuck keys
                self.cleanup_stuck_keys()
                
                # Force reset if inactive with keys held
                if (current_time - self.last_activity > 5.0 and self.key_states):
                    if self.debug_keys:
                        self.logger.warning("🚨 Long inactivity - force reset")
                    self.force_reset()
                
                # Schedule next check
                threading.Timer(self.cleanup_interval, monitor).start()
                
            except Exception as e:
                self.logger.error(f"Monitor error: {e}")
        
        monitor()


class SelectionAutocompleteFastCombo:
    def __init__(self, config_file="autocomplete_config.ini"):
        self.load_config(config_file)
        self.setup_logging()
        
        # Initialize fast key tracker
        self.key_tracker = FastKeyTracker(self.logger, self.config)
        
        # Setup combinations
        self.setup_key_combinations()
        
        # State
        self.last_completion_time = 0
        self.popup_active = False
        
        # Statistics
        self.stats = {
            'quick_requests': 0,
            'popup_requests': 0,
            'successful_completions': 0,
            'failed_completions': 0,
            'key_resets': 0,
            'invalid_combinations': 0
        }
        
        self.logger.info("Selection Autocomplete (Fast Combo) initialized")
        self.logger.info(f"Combination timeout: {self.combination_timeout}s")
        self.logger.info(f"Completion cooldown: {self.completion_cooldown}s")
    
    def load_config(self, config_file):
        """Load configuration from file"""
        config = configparser.ConfigParser()
        
        if not os.path.exists(config_file):
            self.create_default_config(config_file)
        
        config.read(config_file)
        self.config = config
        
        # Ollama settings
        self.ollama_host = config.get('ollama', 'host', fallback='100.73.210.57')
        self.ollama_port = config.getint('ollama', 'port', fallback=11434)
        self.model_name = config.get('ollama', 'model_name', fallback='hf.co/TheBloke/LLaMA-13b-GGUF:Q5_K_M')
        self.ollama_url = f"http://{self.ollama_host}:{self.ollama_port}/api/generate"
        
        # Completion settings
        self.context_tokens = config.getint('completion', 'context_tokens', fallback=1024)
        self.quick_tokens = config.getint('completion', 'quick_tokens', fallback=80)
        self.popup_tokens = config.getint('completion', 'popup_tokens', fallback=80)
        self.temperature = config.getfloat('completion', 'temperature', fallback=0.3)
        self.popup_options_count = config.getint('completion', 'popup_options_count', fallback=5)
        
        # Key bindings
        self.quick_keys = config.get('keybindings', 'quick_completion', fallback='ctrl+space')
        self.popup_keys = config.get('keybindings', 'popup_completion', fallback='shift+f1')
        
        # Timing settings
        self.combination_timeout = config.getfloat('timing', 'combination_timeout', fallback=0.8)
        self.completion_cooldown = config.getfloat('timing', 'completion_cooldown', fallback=0.3)
        
        # Injection settings
        self.injection_delay = config.getfloat('injection', 'injection_delay', fallback=0.1)
        self.typing_delay = config.getint('injection', 'typing_delay', fallback=25)
        self.injection_timeout = config.getint('injection', 'injection_timeout', fallback=15)
        
        # Logging
        self.log_level = config.get('logging', 'log_level', fallback='INFO')
        self.log_file = os.path.expanduser(config.get('logging', 'log_file', fallback='~/.local/share/autocomplete/fast_combo.log'))
    
    def create_default_config(self, config_file):
        """Create comprehensive default config"""
        config_content = """[ollama]
# Ollama server settings
host = 100.73.210.57
port = 11434
model_name = hf.co/TheBloke/LLaMA-13b-GGUF:Q5_K_M

[completion]
# Token settings for AI generation
context_tokens = 1024
quick_tokens = 80
popup_tokens = 80
temperature = 0.3
popup_options_count = 5

[keybindings]
# Key combinations - use + to separate keys
# Available keys: ctrl, shift, alt, space, tab, enter, f1-f12, a-z
# Examples: ctrl+space, shift+f1, ctrl+alt+tab, f5, ctrl+shift+s
quick_completion = ctrl+space
popup_completion = shift+f1

[timing]
# Key combination timing (in seconds)
combination_timeout = 0.8
# How long to wait between completions
completion_cooldown = 0.3
# Maximum time a single key can be held before auto-release
max_key_hold_time = 2.0
# How often to check for stuck keys
cleanup_interval = 0.5

[popup]
# Popup window settings
window_width = 850
window_height = 500
max_preview_length = 150
show_option_numbers = true

[injection]
# Text injection settings
injection_delay = 0.1
typing_delay = 25
injection_timeout = 15

[debug]
# Debug settings - enable for troubleshooting
key_tracking = false
show_timing = false
log_combinations = true

[logging]
# Logging configuration
log_level = INFO
log_file = ~/.local/share/autocomplete/fast_combo.log
max_log_size_mb = 10
"""
        
        os.makedirs(os.path.dirname(os.path.abspath(config_file)), exist_ok=True)
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        print(f"✅ Created comprehensive config: {config_file}")
        print("   Edit timing.combination_timeout to adjust key combination speed")
    
    def setup_logging(self):
        """Setup logging with rotation"""
        log_dir = os.path.dirname(self.log_file)
        os.makedirs(log_dir, exist_ok=True)
        
        # Setup rotating log
        from logging.handlers import RotatingFileHandler
        
        max_bytes = self.config.getint('logging', 'max_log_size_mb', fallback=10) * 1024 * 1024
        
        file_handler = RotatingFileHandler(
            self.log_file, 
            maxBytes=max_bytes, 
            backupCount=3
        )
        
        console_handler = logging.StreamHandler()
        
        logging.basicConfig(
            level=getattr(logging, self.log_level),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[file_handler, console_handler]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def setup_key_combinations(self):
        """Setup key combinations"""
        self.logger.info("🔧 Setting up fast key combinations...")
        
        # Parse combinations
        quick_combo = self.parse_key_combination(self.quick_keys)
        popup_combo = self.parse_key_combination(self.popup_keys)
        
        # Add with validation
        quick_ok = self.key_tracker.add_combination('quick', quick_combo)
        popup_ok = self.key_tracker.add_combination('popup', popup_combo)
        
        if not quick_ok:
            self.logger.error(f"❌ Invalid quick combination: {self.quick_keys}")
            self.stats['invalid_combinations'] += 1
        
        if not popup_ok:
            self.logger.error(f"❌ Invalid popup combination: {self.popup_keys}")
            self.stats['invalid_combinations'] += 1
        
        # Emergency reset
        reset_combo = [Key.ctrl, Key.alt, keyboard.KeyCode.from_char('r')]
        self.key_tracker.add_combination('reset', reset_combo)
    
    def parse_key_combination(self, key_string):
        """Parse key combination string"""
        keys = []
        parts = [part.strip().lower() for part in key_string.split('+')]
        
        for part in parts:
            if part == 'ctrl':
                keys.append(Key.ctrl)
            elif part == 'shift':
                keys.append(Key.shift)
            elif part == 'alt':
                keys.append(Key.alt)
            elif part == 'space':
                keys.append(Key.space)
            elif part == 'tab':
                keys.append(Key.tab)
            elif part == 'enter':
                keys.append(Key.enter)
            elif part.startswith('f') and len(part) > 1 and part[1:].isdigit():
                f_num = int(part[1:])
                if 1 <= f_num <= 12:
                    keys.append(getattr(Key, f'f{f_num}'))
            elif len(part) == 1 and part.isalpha():
                keys.append(keyboard.KeyCode.from_char(part))
            else:
                self.logger.warning(f"⚠️ Unknown key: {part}")
        
        return keys
    
    def get_selected_text_for_context(self):
        """Get selected text for context"""
        try:
            original_clipboard = ""
            try:
                original_clipboard = pyperclip.paste()
            except:
                pass
            
            # Copy selection
            subprocess.run(['xdotool', 'key', '--clearmodifiers', 'ctrl+c'], timeout=2.0)
            time.sleep(0.15)
            
            try:
                context_text = pyperclip.paste()
            except:
                context_text = ""
            
            # Restore clipboard
            try:
                if original_clipboard:
                    pyperclip.copy(original_clipboard)
            except:
                pass
            
            if context_text and context_text.strip() and len(context_text.strip()) > 3:
                self.logger.info(f"✅ Context: '{context_text[:60]}...'")
                return context_text.strip()
            
            return None
        except Exception as e:
            self.logger.error(f"Context extraction error: {e}")
            return None
    
    def move_cursor_to_end(self):
        """Move cursor to end of selection"""
        try:
            subprocess.run(['xdotool', 'key', '--clearmodifiers', 'Right'], timeout=1.0)
            time.sleep(0.05)
            return True
        except:
            return False
    
    def call_ollama_unified(self, prompt, max_tokens, temperature=None):
        """Unified Ollama call"""
        try:
            if temperature is None:
                temperature = self.temperature
            
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                    "num_ctx": self.context_tokens,
                    "stop": []
                }
            }
            
            response = requests.post(self.ollama_url, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                completion = result.get('response', '').strip()
                completion = self.clean_completion_minimal(completion)
                return completion
            
            return None
        except Exception as e:
            self.logger.error(f"Ollama error: {e}")
            return None
    
    def clean_completion_minimal(self, text):
        """Minimal text cleaning"""
        if not text:
            return ""
        
        # Remove artifacts but preserve content
        text = re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', text)
        text = re.sub(r'```[^`]*```', '', text)
        text = re.sub(r'\n+', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        
        if text and not text.startswith(' '):
            text = ' ' + text
        
        return text.strip()
    
    def generate_multiple_options(self, context, count=5):
        """Generate multiple completion options"""
        options = []
        temperatures = [0.2, 0.3, 0.4, 0.5, 0.6]
        
        self.logger.info(f"🎲 Generating {count} options...")
        
        for i in range(count):
            temp = temperatures[i] if i < len(temperatures) else 0.3
            completion = self.call_ollama_unified(context, self.popup_tokens, temperature=temp)
            
            if completion and len(completion.strip()) > 10:
                if completion not in options:
                    options.append(completion)
                    self.logger.info(f"✅ Option {len(options)}: '{completion[:50]}...'")
        
        return options
    
    def inject_text(self, text):
        """Inject text with configurable settings"""
        if not text:
            return False
        
        try:
            time.sleep(self.injection_delay)
            result = subprocess.run([
                'xdotool', 'type', '--delay', str(self.typing_delay), '--clearmodifiers', text
            ], timeout=self.injection_timeout)
            
            if result.returncode == 0:
                return True
        except:
            pass
        
        # Clipboard fallback
        try:
            original = pyperclip.paste()
            pyperclip.copy(text)
            subprocess.run(['xdotool', 'key', '--clearmodifiers', 'ctrl+v'], timeout=5)
            time.sleep(0.3)
            pyperclip.copy(original)
            return True
        except:
            return False
    
    def show_popup_options(self, context):
        """Show popup with completion options"""
        self.popup_active = True
        
        try:
            options = self.generate_multiple_options(context, self.popup_options_count)
            
            if not options:
                self.logger.error("❌ No options generated")
                self.popup_active = False
                return
            
            def on_selection(selected_option):
                self.popup_active = False
                if selected_option:
                    success = self.inject_text(selected_option)
                    if success:
                        self.stats['successful_completions'] += 1
                        self.logger.info(f"✅ Selected: '{selected_option[:50]}...'")
                    else:
                        self.stats['failed_completions'] += 1
                
                # Force reset keys after popup
                self.key_tracker.force_reset()
            
            popup = CompletionPopup(options, on_selection, self.config)
            popup.show()
            
        except Exception as e:
            self.logger.error(f"Popup error: {e}")
            self.popup_active = False
    
    def on_key_press(self, key):
        """Handle key press"""
        if self.popup_active:
            return
        
        combination = self.key_tracker.on_key_press(key)
        
        if combination:
            if combination == 'reset':
                self.handle_emergency_reset()
            else:
                self.handle_completion(combination)
    
    def on_key_release(self, key):
        """Handle key release"""
        if not self.popup_active:
            self.key_tracker.on_key_release(key)
    
    def handle_emergency_reset(self):
        """Emergency reset"""
        self.logger.warning("🚨 Emergency reset!")
        self.key_tracker.force_reset()
        self.stats['key_resets'] += 1
        self.popup_active = False
        print("\n🔄 Keys reset!")
    
    def handle_completion(self, completion_type):
        """Handle completion request"""
        current_time = time.time()
        
        if current_time - self.last_completion_time < self.completion_cooldown:
            return
        
        self.last_completion_time = current_time
        
        if completion_type == 'quick':
            self.stats['quick_requests'] += 1
        elif completion_type == 'popup':
            self.stats['popup_requests'] += 1
        
        if completion_type == 'popup':
            threading.Thread(target=self._popup_worker, daemon=True).start()
        else:
            threading.Thread(target=self._quick_worker, daemon=True).start()
    
    def _popup_worker(self):
        """Popup completion worker"""
        try:
            context = self.get_selected_text_for_context()
            if not context:
                return
            
            self.move_cursor_to_end()
            self.show_popup_options(context)
            
        except Exception as e:
            self.logger.error(f"Popup worker error: {e}")
    
    def _quick_worker(self):
        """Quick completion worker"""
        try:
            context = self.get_selected_text_for_context()
            if not context:
                return
            
            self.move_cursor_to_end()
            completion = self.call_ollama_unified(context, self.quick_tokens)
            
            if completion:
                success = self.inject_text(completion)
                if success:
                    self.stats['successful_completions'] += 1
                    self.logger.info(f"✅ Quick: '{completion[:50]}...'")
                else:
                    self.stats['failed_completions'] += 1
            
        except Exception as e:
            self.logger.error(f"Quick worker error: {e}")
    
    def test_connection(self):
        """Test Ollama connection"""
        try:
            result = self.call_ollama_unified("Test", 5)
            return result is not None
        except:
            return False
    
    def print_stats(self):
        """Print comprehensive statistics"""
        print("\n" + "="*70)
        print("📊 SELECTION AUTOCOMPLETE STATISTICS")
        print("="*70)
        
        # Application stats
        print("Application:")
        print(f"   Quick requests: {self.stats['quick_requests']}")
        print(f"   Popup requests: {self.stats['popup_requests']}")
        print(f"   Successful completions: {self.stats['successful_completions']}")
        print(f"   Failed completions: {self.stats['failed_completions']}")
        print(f"   Emergency resets: {self.stats['key_resets']}")
        
        # Key tracker stats
        key_stats = self.key_tracker.get_stats()
        print("\nKey Tracking:")
        print(f"   Total key presses: {key_stats['total_key_presses']}")
        print(f"   Combinations detected: {key_stats['combinations_detected']}")
        print(f"   Combinations timed out: {key_stats['combinations_timeout']}")
        print(f"   Stuck keys cleaned: {key_stats['stuck_keys_cleaned']}")
        
        # Success rates
        total_requests = self.stats['quick_requests'] + self.stats['popup_requests']
        if total_requests > 0:
            success_rate = (self.stats['successful_completions'] / total_requests) * 100
            print(f"\nSuccess rate: {success_rate:.1f}%")
        
        if key_stats['total_key_presses'] > 0:
            combo_rate = (key_stats['combinations_detected'] / key_stats['total_key_presses']) * 100
            timeout_rate = (key_stats['combinations_timeout'] / key_stats['total_key_presses']) * 100
            print(f"Combination detection rate: {combo_rate:.2f}%")
            print(f"Timeout rate: {timeout_rate:.2f}%")
        
        print("="*70)
    
    def start(self):
        """Start the autocomplete service"""
        if not self.test_connection():
            print("❌ Cannot connect to Ollama")
            return False
        
        print("🚀 SELECTION AUTOCOMPLETE - FAST KEY COMBINATIONS")
        print("="*62)
        print("⚡ FAST TIMING FEATURES:")
        print(f"   ✅ Key combination timeout: {self.combination_timeout}s")
        print(f"   ✅ Completion cooldown: {self.completion_cooldown}s")
        print(f"   ✅ Automatic cleanup every {self.key_tracker.cleanup_interval}s")
        print(f"   ✅ Max key hold time: {self.key_tracker.max_key_hold_time}s")
        print("")
        print("🎯 KEY COMBINATIONS:")
        print(f"   {self.quick_keys.upper():15} → Quick completion")
        print(f"   {self.popup_keys.upper():15} → Popup options")
        print("   CTRL+ALT+R    → Emergency reset")
        print("")
        print("⚙️ CURRENT SETTINGS:")
        print(f"   Server: {self.ollama_host}:{self.ollama_port}")
        print(f"   Tokens: {self.quick_tokens} (both modes)")
        print(f"   Temperature: {self.temperature}")
        print(f"   Popup options: {self.popup_options_count}")
        print("")
        print("🔧 TIMING CONFIGURATION:")
        print(f"   combination_timeout = {self.combination_timeout}s (in config)")
        print("   └─ How fast you must complete key combination")
        print(f"   completion_cooldown = {self.completion_cooldown}s")
        print("   └─ Delay between completions")
        print("")
        print("🔍 DEBUG OPTIONS:")
        debug_keys = self.config.getboolean('debug', 'key_tracking', fallback=False)
        debug_timing = self.config.getboolean('debug', 'show_timing', fallback=False)
        print(f"   Key tracking: {'🟢 ON' if debug_keys else '🔴 OFF'}")
        print(f"   Timing debug: {'🟢 ON' if debug_timing else '🔴 OFF'}")
        print("   (Edit [debug] section in config to enable)")
        print("")
        print("💡 TO ADJUST SPEED:")
        print("   Edit autocomplete_config.ini → [timing] → combination_timeout")
        print("   Lower = faster (e.g., 0.5s), Higher = more forgiving (e.g., 1.2s)")
        print("="*62)
        print("Press Ctrl+C to stop and view statistics")
        print("")
        
        try:
            with Listener(on_press=self.on_key_press, on_release=self.on_key_release) as listener:
                listener.join()
        except KeyboardInterrupt:
            print("\n🛑 Stopping...")
            self.print_stats()
            return True

def main():
    try:
        subprocess.run(['which', 'xdotool'], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("❌ Missing dependency: xdotool")
        print("Install with: sudo apt install xdotool")
        return 1
    
    autocomplete = SelectionAutocompleteFastCombo()
    return 0 if autocomplete.start() else 1

if __name__ == "__main__":
    sys.exit(main())