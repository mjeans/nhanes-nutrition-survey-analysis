"""Accessible estimation plots generated directly from survey result tables."""
from html import escape
from math import ceil, floor
from pathlib import Path

NAVY, TEAL, GRAY = "#142d42", "#087e83", "#687b89"

def text(x, y, value, size=16, color=NAVY, anchor="start", weight="400"):
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{weight}">{escape(str(value))}</text>'

def line(x1,y1,x2,y2,color="#dae3e9",width=1):
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width}"/>'

def start(title, subtitle, height, description):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>',
            '<rect width="100%" height="100%" fill="white"/><g font-family="Arial, sans-serif">',
            text(40,46,title,27,weight="700"),text(40,76,subtitle,16,GRAY),line(40,100,960,100)]

def save(path, parts, height, caption):
    parts += [text(40,height-24,caption,14,GRAY),'</g></svg>']
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text('\n'.join(parts)+'\n',encoding='utf-8',newline='\n')

def density_by_age(path, estimates, nutrient):
    measure = 'Fiber (g per 1,000 kcal)' if nutrient == 'fiber' else 'Sodium (mg per 1,000 kcal)'
    rows=estimates.loc[(estimates.group_type=='Age group') & (estimates.measure==measure)].set_index('group').loc[['20-39','40-59','60+']].reset_index()
    unit='g' if nutrient=='fiber' else 'mg'
    step=.5 if nutrient=='fiber' else 50
    low=floor(rows.lower_95.min()/step)*step-step
    high=ceil(rows.upper_95.max()/step)*step+step
    sx=lambda x:210+(float(x)-low)/(high-low)*420
    height=480
    parts=start(f'Survey-weighted {nutrient} density by age',
                'NHANES 2017–2018 | adults with two reliable dietary recalls',height,
                'Horizontal points are weighted means, with Taylor-linearized t-based 95% confidence intervals. Age labels include unweighted sample size. The axis is focused, not zero-based.')
    parts += [text(710,137,'Mean (95% CI)',15,GRAY),text(930,137,'df',15,GRAY,'end')]
    for i in range(round((high-low)/step)+1):
        v=low+i*step
        parts += [line(sx(v),158,sx(v),360),text(sx(v),390,f'{v:g}',14,GRAY,'middle')]
    for i,row in rows.iterrows():
        y=185+i*76
        digits=2 if nutrient=='fiber' else 1
        label=f'{row.estimate:.{digits}f} ({row.lower_95:.{digits}f}, {row.upper_95:.{digits}f})'
        parts += [text(40,y-2,f'{row.group} years',19,weight='700'),text(40,y+22,f'n = {int(row.unweighted_n):,}',14,GRAY),
                  line(sx(row.lower_95),y,sx(row.upper_95),y,TEAL,3),
                  f'<circle cx="{sx(row.estimate):.1f}" cy="{y}" r="7" fill="{TEAL}"/>',
                  text(710,y+5,label,16),text(930,y+5,int(row.design_df),16,GRAY,'end')]
    parts.append(text(420,426,f'{unit} per 1,000 kcal (focused scale)',16,GRAY,'middle'))
    save(path,parts,height,'Source: CDC/NCHS public-use dietary files. Group intervals do not test between-group differences.')

def coefficients(path, regressions):
    height=865
    parts=start('Adjusted nutrient-density associations',
                'NHANES 2017–2018 | survey-weighted descriptive regressions',height,
                'Two separate unit scales display coefficients and t-based 95% confidence intervals. The intercept is omitted. Vertical lines mark zero association; these are not causal effects.')
    labels={'Age 40-59 vs 20-39':'Age 40–59 vs 20–39', 'Age 60+ vs 20-39':'Age 60+ vs 20–39',
            'Female vs male':'Female vs male', 'Family income-to-poverty ratio (per unit)':'Income-to-poverty ratio (+1)'}
    for panel,measure in enumerate(regressions.outcome.unique()):
        rows=regressions.loc[(regressions.outcome==measure) & ~regressions.term.str.startswith('Intercept')].reset_index(drop=True)
        top=155+panel*335
        low=min(0,float(rows.lower_95.min()));high=max(0,float(rows.upper_95.max()))
        pad=(high-low)*.12 or 1
        low-=pad;high+=pad
        sx=lambda v:365+(float(v)-low)/(high-low)*285
        parts += [text(40,top,measure,21,weight='700'),text(715,top,'Coefficient (95% CI)',14,GRAY),
                  line(sx(0),top+22,sx(0),top+241,GRAY,1.5)]
        for i,row in rows.iterrows():
            y=top+48+i*52
            parts += [text(40,y+5,labels[row.term],16),line(sx(row.lower_95),y,sx(row.upper_95),y,TEAL,3),
                      f'<circle cx="{sx(row.estimate):.1f}" cy="{y}" r="6" fill="{TEAL}"/>',
                      text(715,y+5,f'{row.estimate:.2f} ({row.lower_95:.2f}, {row.upper_95:.2f})',15)]
        for value in (low,0,high):
            parts.append(text(sx(value),top+264,f'{value:.1f}',14,GRAY,'middle'))
        parts.append(text(40,top+295,f'Complete-case n = {int(rows.unweighted_n.iloc[0]):,}; residual design df = {int(rows.residual_df.iloc[0])}',14,GRAY))
    save(path,parts,height,'Adjusted for age group, sex, and income ratio. Cross-sectional associations; measurement error remains.')
