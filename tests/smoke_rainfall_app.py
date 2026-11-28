import os, sys, tempfile
from pathlib import Path
import pandas as pd
from streamlit.testing.v1 import AppTest
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'tests')]
from test_rainfall_entry import fixture
import streamlit
streamlit.logger.get_logger('streamlit').setLevel('ERROR')
with tempfile.TemporaryDirectory() as tmp:
    os.chdir(tmp)
    path=Path('data_curah_hujan.parquet')
    initial=fixture()
    initial.to_parquet(path,index=False)
    for k in ('GITHUB_TOKEN','github_token'):
        os.environ.pop(k,None)
    at=AppTest.from_file(str(root/'app.py'),default_timeout=45).run()
    def checked():
        assert not at.exception, list(at.exception)
    def radio(label):
        return next(r for r in at.radio if r.label == label)
    def assert_unchanged(before):
        assert path.read_bytes() == before
        assert not Path('data_curah_hujan_backup.parquet').exists()
        assert not Path('manual_records_log.csv').exists()
    def month_a():
        data=pd.read_parquet(path)
        return data.loc[(data.Stasiun=='Uji A') & (data.Bulan==1)].set_index('Hari')
    checked()
    before=path.read_bytes()
    next(b for b in at.button if 'Simpan Data Harian' in b.label).click().run()
    checked()
    assert any('Isi hasil pengukuran' in e.value for e in at.error)
    assert_unchanged(before)
    radio('Pilih Metode Input:').set_value('Input Matriks 1 Bulan Penuh (Grid Editor)').run()
    checked()
    assert at.number_input(key='num_ch_tbl_Uji A_2026_1_2_nrm').value is None
    assert at.number_input(key='num_ch_tbl_Uji A_2026_1_1_nrm').value == 0
    at.button(key='btn_save_interactive').click().run()
    checked()
    assert_unchanged(before)
    assert any('Tidak ada perubahan' in e.value for e in at.info)
    at.number_input(key='num_ch_tbl_Uji A_2026_1_5_nrm').set_value(12.5)
    at.button(key='btn_save_interactive').click().run()
    checked()
    m=month_a()
    assert m.loc[5,'Curah_Hujan']==12.5 and pd.isna(m.loc[2,'Curah_Hujan']) and m.loc[1,'Curah_Hujan']==0 and m.loc[3,'Status']=='RUSAK',m
    assert any('berhasil disimpan' in e.value for e in at.success)
    at.radio(key='bulk_view_style_choice').set_value('📊 Grid Spreadsheet (Data Editor)').run()
    checked()
    before_grid=path.read_bytes()
    log=Path('manual_records_log.csv').read_bytes()
    at.button(key='btn_save_grid').click().run()
    checked()
    assert path.read_bytes()==before_grid and Path('manual_records_log.csv').read_bytes()==log
    at.session_state['editor_Uji A_2026_1']={'edited_rows':{1:{'Curah Hujan (mm)':4.5},3:{'Status Alat':'Belum Ada Data'}},'added_rows':[],'deleted_rows':[]}
    at.button(key='btn_save_grid').click().run()
    checked()
    m=month_a()
    assert m.loc[2,'Curah_Hujan']==4.5 and m.loc[2,'Status']=='Normal' and pd.isna(m.loc[4,'Curah_Hujan']) and m.loc[4,'Status']=='Belum Ada Data' and m.loc[1,'Curah_Hujan']==0 and m.loc[3,'Status']=='RUSAK',m
    from pandas.testing import assert_frame_equal
    output=pd.read_parquet(path)
    keep=lambda f:f.loc[(f.Stasiun!='Uji A') | (f.Bulan!=1)].reset_index(drop=True)
    assert_frame_equal(keep(output),keep(initial))
    before_import=path.read_bytes()
    for name in ('Unggah Excel','Unggah CSV','Tempel teks CSV'):
        next(w for w in at.sidebar.selectbox if w.label=='Sumber data').select(name).run()
        checked()
        assert not any('Simpan Data Harian' in b.label or b.key in ('btn_save_grid','btn_save_interactive') for b in at.button)
    at.sidebar.text_area[0].set_value("Tahun,2026,No. Stasiun :,Uji Impor\nTgl,Jan\n1,17.5\n").run()
    checked()
    assert any('hanya untuk dilihat dan diekspor' in e.value for e in at.info)
    assert not any('Simpan Data Harian' in b.label or b.key in ('btn_save_grid','btn_save_interactive') for b in at.button)
    assert path.read_bytes()==before_import
    next(w for w in at.sidebar.selectbox if w.label=='Sumber data').select('Data tersimpan').run()
    checked()
    assert any(r.label=='Pilih Metode Input:' for r in at.radio)
    print('PASS: daily blank validation; interactive+grid no-op and partial saves; zero, blank and broken distinct; untouched station/month; imported CSV read-only; storage source restored.')
