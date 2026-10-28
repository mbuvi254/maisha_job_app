(() => {
  const data = document.getElementById('taxonomy-data');
  const industry = document.getElementById('industry_id');
  const category = document.getElementById('category_id');
  if (!data || !industry || !category) return;
  const taxonomy = JSON.parse(data.textContent);
  industry.addEventListener('change', () => {
    const previous = category.value;
    category.replaceChildren(new Option('All categories', ''));
    taxonomy.filter(group => !industry.value || String(group.industry.id) === industry.value).forEach(group => {
      const options = document.createElement('optgroup');
      options.label = group.industry.name;
      group.categories.forEach(item => options.append(new Option(item.name, item.id)));
      category.append(options);
    });
    if (Array.from(category.options).some(option => option.value === previous)) category.value = previous;
  });
})();
