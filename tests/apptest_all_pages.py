import sys, numpy as np, pandas as pd
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parents[1]))
from streamlit.testing.v1 import AppTest
from ews.data_io import load_sample
obs, gl = load_sample(__import__('pathlib').Path(__file__).parents[1] / 'data' / 'sample')
pages = ['pages/0_Accueil.py','pages/1_Donnees.py','pages/2_Bassin.py','pages/3_Performance.py','pages/4_Qualite_prevision.py',
         'pages/5_Similarite.py','pages/6_Frequences.py','pages/8_Configuration.py','pages/7_Prevision.py']
for p in pages:
    at = AppTest.from_file('../app.py', default_timeout=180)
    at.session_state['obs'] = obs; at.session_state['glofas'] = gl; at.session_state['source'] = 'exemple'
    at.run()
    at.switch_page(p); at.run()
    print(p, 'exceptions:', [e.value for e in at.exception][:2], '| errors:', [e.value for e in at.error][:2], '| warnings:', len(at.warning))
# operational page with manual forecast (no internet here)
at = AppTest.from_file('../app.py', default_timeout=180)
at.session_state['obs'] = obs; at.session_state['glofas'] = gl; at.session_state['source'] = 'exemple'
today = pd.Timestamp('2026-10-09')
idx = pd.date_range(today - pd.Timedelta(days=7), periods=15, freq='D')
mk = lambda base: pd.DataFrame({'river_discharge': base + np.linspace(0, 20, 15), 'river_discharge_min': base - 5 + np.linspace(0, 20, 15),
       'river_discharge_p25': base - 2 + np.linspace(0, 20, 15), 'river_discharge_median': base + np.linspace(0, 20, 15),
       'river_discharge_p75': base + 3 + np.linspace(0, 20, 15), 'river_discharge_max': base + 8 + np.linspace(0, 20, 15)}, index=idx)
at.session_state['manual_fc'] = {'RUSIZI': mk(500.0), 'KABURANTWA': mk(15.0), 'MPANDA': mk(50.0)}
at.session_state['q_RUSIZI'] = 255.0; at.session_state['q_KABURANTWA'] = 30.0; at.session_state['q_MPANDA'] = 9.0
at.run(); at.switch_page('pages/7_Prevision.py'); at.run()
at.date_input[0].set_value(today.date()).run()
at.button[0].click().run()
print('OP exceptions', [e.value for e in at.exception], 'warnings', [w.value for w in at.warning])
for df in at.dataframe: print(df.value.head(8).to_string()[:1800]); print('---')
