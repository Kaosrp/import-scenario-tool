import streamlit as st
import pandas as pd
import json
import os
from io import BytesIO
from fpdf import FPDF

# Arquivo para salvar e carregar a base de dados
data_file = "cost_config.json"

def load_data():
    if os.path.exists(data_file):
        with open(data_file, "r") as f:
            return json.load(f)
    else:
        return {}

def save_data(data):
    with open(data_file, "w") as f:
        json.dump(data, f, indent=4)

# Função para calcular o custo total por cenário
def calculate_total_cost(data, scenario):
    # Aplica ICMS para cenários que contenham "DI" ou "DDC" no nome
    icms_rate = 0.18 if "DI" in scenario or "DDC" in scenario else 0.0
    custo_icms = data.get('Valor CIF', 0) * icms_rate
    total_cost = data.get('Valor CIF', 0) \
                 + data.get('Frete rodoviário', 0) \
                 + data.get('Armazenagem', 0) \
                 + data.get('Taxa MAPA', 0) \
                 + data.get('Taxas Porto Seco', 0) \
                 + data.get('Desova EAD', 0) \
                 + data.get('Taxa cross docking', 0) \
                 + data.get('Taxa DDC', 0) \
                 + custo_icms
    return total_cost, custo_icms

# Função para exportar o DataFrame para Excel
def to_excel(df: pd.DataFrame):
    output = BytesIO()
    # Usamos o ExcelWriter para escrever o DataFrame em memória
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Cenários', index=True)
        writer.save()
    processed_data = output.getvalue()
    return processed_data

# Função para exportar o DataFrame para PDF usando FPDF
def to_pdf(df: pd.DataFrame):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)

    # Define as dimensões úteis da página para a tabela
    effective_page_width = pdf.w - 2 * pdf.l_margin
    num_cols = len(df.columns)
    col_width = effective_page_width / num_cols
    row_height = 8

    # Adiciona o cabeçalho da tabela
    for col in df.columns:
        pdf.cell(col_width, row_height, str(col), border=1)
    pdf.ln(row_height)

    # Adiciona as linhas do DataFrame
    for index, row in df.iterrows():
        for item in row:
            pdf.cell(col_width, row_height, str(item), border=1)
        pdf.ln(row_height)

    # Gera o PDF para um objeto string (codificado em bytes)
    pdf_data = pdf.output(dest='S').encode('latin1')
    return pdf_data

# Título do app
st.title("Ferramenta de Análise de Cenários de Importação")
option = st.sidebar.selectbox("Escolha uma opção", ["Configuração", "Simulador de Cenários"])

# Carrega os dados da base (JSON)
data = load_data()

# Função para salvar o valor alterado de um campo
def save_value(filial, scenario, field, value):
    if filial not in data:
        data[filial] = {}
    if scenario not in data[filial]:
        data[filial][scenario] = {}
    data[filial][scenario][field] = value
    save_data(data)

if option == "Configuração":
    st.header("Configuração de Base de Custos por Filial")
    filial_names = ["Cuiabá-MT", "Ribeirão Preto-SP", "Uberaba-MG"]
    # Lista de cenários (sem duplicidade)
    scenarios = [
        "DTA Contêiner - Santos", 
        "DTA Cross Docking - Santos", 
        "DI Contêiner - Santos", 
        "DDC - Santos",
        "DTA Contêiner - Paranaguá", 
        "DTA Cross Docking - Paranaguá", 
        "DI Contêiner - Paranaguá", 
        "DDC - Paranaguá"
    ]
    
    # Cria abas para cada filial
    main_tabs = st.tabs(filial_names)
    for main_tab, filial in zip(main_tabs, filial_names):
        with main_tab:
            st.subheader(f"Configuração de Custos - Filial: {filial}")
            if filial not in data:
                data[filial] = {}
            
            # Cria abas para cada cenário
            scenario_tabs = st.tabs(scenarios)
            for scenario_tab, scenario in zip(scenario_tabs, scenarios):
                with scenario_tab:
                    st.subheader(f"{scenario} - {filial}")
                    if scenario not in data[filial]:
                        data[filial][scenario] = {}
                    # Lista de campos para configuração
                    for field in ["Frete rodoviário", "Armazenagem", "Taxa MAPA", 
                                  "Taxas Porto Seco", "Desova EAD", "Taxa cross docking", "Taxa DDC"]:
                        if field not in data[filial][scenario]:
                            data[filial][scenario][field] = 0
                        current_value = data[filial][scenario][field]
                        # Chave única estável (sem uso de uuid)
                        unique_key = f"{filial}_{scenario}_{field}"
                        updated_value = st.number_input(f"{field}", min_value=0, value=current_value, key=unique_key)
                        if updated_value != current_value:
                            save_value(filial, scenario, field, updated_value)
                            
    st.success("Configuração atualizada e salva automaticamente!")

elif option == "Simulador de Cenários":
    st.header("Simulador de Cenários de Importação")
    filial_selected = st.selectbox("Selecione a Filial", ["Cuiabá-MT", "Ribeirão Preto-SP", "Uberaba-MG"])
    
    st.subheader("Cálculo do Valor CIF")
    valor_fob_usd = st.number_input("Valor FOB da Mercadoria (USD)", min_value=0.0, value=0.0)
    frete_internacional_usd = st.number_input("Frete Internacional (USD)", min_value=0.0, value=0.0)
    taxas_frete_brl = st.number_input("Taxas do Frete (BRL)", min_value=0.0, value=0.0)
    taxa_cambio = st.number_input("Taxa de Câmbio (USD -> BRL)", min_value=0.0, value=5.0)
    
    # Cálculo do valor CIF
    valor_cif = (valor_fob_usd + frete_internacional_usd) * taxa_cambio + taxas_frete_brl
    st.write(f"### Valor CIF Calculado: R$ {valor_cif:,.2f}")
    
    costs = {}
    if filial_selected in data:
        for scenario, fields in data[filial_selected].items():
            # Bypass: ignora o cenário "teste" (case insensitive)
            if scenario.lower() == "teste":
                continue
            scenario_data = fields.copy()
            scenario_data['Valor CIF'] = valor_cif
            total_cost, custo_icms = calculate_total_cost(scenario_data, scenario)
            costs[scenario] = {
                "Custo Total": total_cost,
                "ICMS (Calculado)": custo_icms,
                "Frete Rodoviário": scenario_data.get('Frete rodoviário', 0),
                "Taxa MAPA": scenario_data.get('Taxa MAPA', 0),
                "Armazenagem": scenario_data.get('Armazenagem', 0),
                "Taxas Porto Seco": scenario_data.get('Taxas Porto Seco', 0),
                "Desova EAD": scenario_data.get('Desova EAD', 0),
                "Taxa Cross Docking": scenario_data.get('Taxa cross docking', 0),
                "Taxa DDC": scenario_data.get('Taxa DDC', 0)
            }
    
    if costs:
        st.write("### Comparação de Cenários para a Filial Selecionada")
        df = pd.DataFrame(costs).T.sort_values(by="Custo Total")
        st.dataframe(df)

        st.write(f"O melhor cenário para {filial_selected} é **{df.index[0]}** com custo total de **R$ {df.iloc[0]['Custo Total']:,.2f}**.")

        # Botão para exportar a análise para Excel
        excel_data = to_excel(df)
        st.download_button(
            label="Exportar para Excel",
            data=excel_data,
            file_name="analise_cenarios.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Botão para exportar a análise para PDF
        pdf_data = to_pdf(df)
        st.download_button(
            label="Exportar para PDF",
            data=pdf_data,
            file_name="analise_cenarios.pdf",
            mime="application/pdf"
        )
    else:
        st.warning("Nenhuma configuração encontrada para a filial selecionada. Por favor, configure a base de custos na aba Configuração.")

