// Additional JavaScript to enhance the votes per day input fields
document.addEventListener('DOMContentLoaded', function() {
  // Function to set up the tooltip for votes per day inputs
  function setupVotesPerDayTooltip() {
    // For the add user form
    const votesPerDayInput = document.getElementById('votesPerDay');
    if (votesPerDayInput) {
      // Show tooltip on focus
      votesPerDayInput.addEventListener('focus', function() {
        showTooltip(this, 'Choose how many times per day to vote for this author (1-10)');
      });
      
      // Hide tooltip on blur
      votesPerDayInput.addEventListener('blur', function() {
        hideTooltip();
      });
    }
    
    // For edit forms (they may not exist yet, will be handled when modal opens)
    document.addEventListener('click', function(e) {
      if (e.target && e.target.id === 'editVotesPerDay') {
        e.target.addEventListener('focus', function() {
          showTooltip(this, 'Choose how many times per day to vote for this author (1-10)');
        });
        
        e.target.addEventListener('blur', function() {
          hideTooltip();
        });
      }
    });
  }
  
  // Create and show tooltip
  function showTooltip(element, text) {
    // Remove any existing tooltips
    hideTooltip();
    
    // Create tooltip
    const tooltip = document.createElement('div');
    tooltip.className = 'votes-tooltip';
    tooltip.textContent = text;
    
    // Position the tooltip
    const rect = element.getBoundingClientRect();
    tooltip.style.position = 'absolute';
    tooltip.style.top = (rect.top - 40) + 'px';
    tooltip.style.left = rect.left + 'px';
    
    // Add to document
    document.body.appendChild(tooltip);
    
    // Add animation classes
    setTimeout(() => {
      tooltip.classList.add('show');
    }, 10);
  }
  
  // Hide tooltip
  function hideTooltip() {
    const tooltip = document.querySelector('.votes-tooltip');
    if (tooltip) {
      tooltip.classList.remove('show');
      setTimeout(() => {
        tooltip.remove();
      }, 300);
    }
  }
  
  // Set up tooltips
  setupVotesPerDayTooltip();
});
