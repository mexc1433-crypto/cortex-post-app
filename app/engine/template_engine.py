"""
Template Engine for Cortex Post
Renders message templates with dynamic variables from provider data.
Supports: {{variable}}, {{variable|format}}, conditional blocks {{#if condition}}...{{/if}}
"""
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

class TemplateEngine:
    """Renders templates with dynamic variables."""
    
    # Pattern for {{variable}} and {{variable|filter}}
    VAR_PATTERN = re.compile(r'\{\{(\w+)(?:\|(\w+))?\}\}')
    
    # Pattern for {{#if variable}}...{{/if}}
    IF_PATTERN = re.compile(r'\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}', re.DOTALL)
    
    # Pattern for {{#if variable}}...{{else}}...{{/if}}
    IF_ELSE_PATTERN = re.compile(r'\{\{#if\s+(\w+)\}\}(.*?)\{\{else\}\}(.*?)\{\{/if\}\}', re.DOTALL)
    
    def render(self, template: str, context: dict[str, Any]) -> str:
        """
        Render a template with context variables.
        
        Args:
            template: Template string with {{variable}} placeholders
            context: Dictionary of variable names to values
        
        Returns:
            Rendered string
        """
        # Process if/else blocks first
        result = self._process_conditionals(template, context)
        
        # Then process variable substitutions
        result = self._process_variables(result, context)
        
        # Clean up any unrendered variables
        result = self._cleanup(result)
        
        return result.strip()
    
    def _process_conditionals(self, template: str, context: dict) -> str:
        """Process {{#if var}}...{{else}}...{{/if}} blocks."""
        # Handle if/else first
        def replace_if_else(match):
            var_name = match.group(1)
            true_block = match.group(2)
            false_block = match.group(3)
            if context.get(var_name):
                return true_block
            return false_block
        
        result = self.IF_ELSE_PATTERN.sub(replace_if_else, template)
        
        # Handle simple if blocks
        def replace_if(match):
            var_name = match.group(1)
            block = match.group(2)
            if context.get(var_name):
                return block
            return ''
        
        result = self.IF_PATTERN.sub(replace_if, result)
        
        return result
    
    def _process_variables(self, template: str, context: dict) -> str:
        """Process {{variable}} and {{variable|filter}} placeholders."""
        def replace_var(match):
            var_name = match.group(1)
            filter_name = match.group(2)
            
            value = context.get(var_name)
            if value is None:
                return match.group(0)  # Keep original if not found
            
            if filter_name:
                value = self._apply_filter(value, filter_name)
            
            return str(value)
        
        return self.VAR_PATTERN.sub(replace_var, template)
    
    def _apply_filter(self, value: Any, filter_name: str) -> Any:
        """Apply a formatting filter to a value."""
        if filter_name == 'upper':
            return str(value).upper()
        elif filter_name == 'lower':
            return str(value).lower()
        elif filter_name == 'comma':
            # Format number with commas: 50000 -> 50,000
            try:
                return f"{float(value):,.2f}"
            except (ValueError, TypeError):
                return value
        elif filter_name == 'percent':
            # Format as percentage: 5.5 -> 5.5%
            try:
                return f"{float(value):+.2f}%"
            except (ValueError, TypeError):
                return value
        elif filter_name == 'round2':
            try:
                return round(float(value), 2)
            except (ValueError, TypeError):
                return value
        elif filter_name == 'currency':
            # Format with currency symbol
            try:
                return f"${float(value):,.2f}"
            except (ValueError, TypeError):
                return value
        elif filter_name == 'date':
            # Format ISO date to readable
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(str(value))
                return dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                return value
        elif filter_name == 'emoji':
            # Add emoji based on value direction
            try:
                num = float(value)
                return "🟢" if num >= 0 else "🔴"
            except (ValueError, TypeError):
                return value
        else:
            logger.warning(f"Unknown filter: {filter_name}")
            return value
    
    def _cleanup(self, text: str) -> str:
        """Remove any unrendered template tags."""
        # Remove double/triple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text
    
    def get_variables(self, template: str) -> list[str]:
        """Extract variable names from a template."""
        return list(set(self.VAR_PATTERN.findall(template)))


template_engine = TemplateEngine()
