/* ============================================
   Домашняя Бухгалтерия - Основной JavaScript
   Файл: static/js/main.js
   ============================================ */

/**
 * Инициализация фильтрации категорий
 * Вызывается после загрузки страницы
 */
function initCategoryFilter() {
    const categorySelect = document.getElementById('category-select');
    const typeRadios = document.querySelectorAll('input[name="type"]');
    
    // Если элемента нет на странице — выходим
    if (!categorySelect || !typeRadios.length) {
        return;
    }
    
    // Данные категорий (передаются из Flask в шаблоне)
    const categories = window.budgetCategories || [];
    
    /**
     * Обновляет список категорий в зависимости от выбранного типа
     */
    function updateCategoryList() {
        const selectedType = document.querySelector('input[name="type"]:checked').value;
        
        // Очищаем список
        categorySelect.innerHTML = '';
        
        // Фильтруем категории по типу
        const filtered = categories.filter(cat => cat.type === selectedType);
        
        // Создаём optgroup
        const optgroup = document.createElement('optgroup');
        optgroup.label = selectedType === 'expense' ? '💸 Расходы' : '💵 Доходы';
        
        // Добавляем опции
        filtered.forEach(cat => {
            const option = document.createElement('option');
            option.value = cat.id;
            option.textContent = cat.name;
            optgroup.appendChild(option);
        });
        
        categorySelect.appendChild(optgroup);
    }
    
    // Слушаем переключение типа транзакции
    typeRadios.forEach(radio => {
        radio.addEventListener('change', updateCategoryList);
    });
    
    // Инициализация при загрузке
    updateCategoryList();
}

/**
 * Инициализация графика расходов (Chart.js)
 * @param {string} canvasId - ID элемента canvas
 * @param {Array} labels - Названия категорий
 * @param {Array} data - Значения расходов
 * @param {Array} colors - Цвета для секторов
 */
function initExpenseChart(canvasId, labels, data, colors) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !data || data.length === 0) {
        return;
    }
    
    const ctx = canvas.getContext('2d');
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors,
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { 
                    position: 'bottom', 
                    labels: { padding: 15, usePointStyle: true } 
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percent = ((value / total) * 100).toFixed(1);
                            return `${label}: ${value.toLocaleString('ru-RU')} ₽ (${percent}%)`;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Автоматический запуск при загрузке страницы
 */
document.addEventListener('DOMContentLoaded', function() {
    initCategoryFilter();
    
    // Инициализация графика (если данные есть в window)
    if (window.chartData) {
        initExpenseChart(
            'expenseChart',
            window.chartData.labels,
            window.chartData.data,
            window.chartData.colors
        );
    }
});