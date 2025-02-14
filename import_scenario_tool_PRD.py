import streamlit as st
import pandas as pd
import json
import os
import altair as alt
from datetime import datetime
import io

# Função para formatar números no padrão "1.234,56"
def format_brl(x):
    try:
        s = "{:,.2f}".format(float(x))
        s = s.replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")
        return s
    except:
        return x

# Injeção de CSS para habilitar scroll horizontal na lista de abas (caso necessário)
st.markdown(
    """
    <style>
    [role="tablist"] {
      overflow-x: auto;
      scroll-behavior: smooth;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Arquivos para os dados e para o histórico de simulações
data_file = "cost_config.json"
history_file = "simulation_history.json"

def load_data():
    if os.path.exists(data_file):
        with open(data_file, "r") as f:
            return json.load(f)
    else:
        return {}

def save_data(data):
    with open(data_file, "w") as f:
        json.dump(data, f, indent=4)

def load_history():
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            return json.load(f)
    else:
        return []

def save_history(history):
    with open(history_file, "w") as f:
        json.dump(history, f, indent=4)


def calculate_total_cost_extended(config, base_values, taxa_cambio, occupancy_fraction):
    """
    Calcula o custo do cenário (exceto impostos de produto).
    - config: dicionário de campos do cenário (ex.: { "Frete rodoviário": {...}, ... }).
    - base_values: ex.: {"Valor CIF": valor_cif_final, "Valor FOB": valor_fob, "Frete Internacional": frete_internacional_rateado}.
    - taxa_cambio: taxa de câmbio (USD -> BRL).
    - occupancy_fraction: fração de ocupação do contêiner (ex.: 0.5 para 50%).
    """
    extra = 0
    for field, conf in config.items():
        if not isinstance(conf, dict):
            cost_value = conf
        else:
            field_type = conf.get("type", "fixed")
            rate_by_occupancy = conf.get("rate_by_occupancy", False)
            if field_type == "fixed":
                cost_value = conf.get("value", 0)
            elif field_type == "percentage":
                base = conf.get("base", "")
                rate = conf.get("rate", 0)
                base_val = base_values.get(base, 0)
                if base.strip().lower() in ["valor fob", "frete internacional"]:
                    base_val = base_val * taxa_cambio
                cost_value = base_val * rate
            else:
                cost_value = 0

            if rate_by_occupancy:
                cost_value *= occupancy_fraction
        
        extra += cost_value
    
    return base_values.get("Valor CIF", 0) + extra


def generate_csv(sim_record):
    results = sim_record["results"]
    df = pd.DataFrame(results).T
    df_formatted = df.applymap(lambda x: format_brl(x) if isinstance(x, (int, float)) else x)
    csv_data = df_formatted.to_csv(index=True, sep=";")
    return csv_data.encode('utf-8')


# ------------------ Função para calcular os impostos de Produto ------------------
def calcular_impostos_produto(produto_info, valor_cif):
    """
    produto_info: dict com as alíquotas do produto, ex.:
      {
        "descricao": "...",
        "ii": 10.0,
        "ipi": 15.0,
        "pis": 2.1,
        "cofins": 9.65
      }
    valor_cif: valor CIF (com seguro) em BRL.

    Bases simples (pode adaptar se sua legislação for diferente):
    - II = aliq_ii% * CIF
    - IPI = aliq_ipi% * (CIF + II)
    - PIS = aliq_pis% * (CIF + II + IPI)
    - COFINS = aliq_cofins% * (CIF + II + IPI)
    Retorna dict com os valores de cada imposto e a soma total.
    """
    ii_aliq = produto_info.get("ii", 0.0) / 100.0
    ipi_aliq = produto_info.get("ipi", 0.0) / 100.0
    pis_aliq = produto_info.get("pis", 0.0) / 100.0
    cofins_aliq = produto_info.get("cofins", 0.0) / 100.0

    valor_ii = valor_cif * ii_aliq
    base_ipi = valor_cif + valor_ii
    valor_ipi = base_ipi * ipi_aliq

    base_pis_cofins = valor_cif + valor_ii + valor_ipi
    valor_pis = base_pis_cofins * pis_aliq
    valor_cofins = base_pis_cofins * cofins_aliq

    total_impostos = valor_ii + valor_ipi + valor_pis + valor_cofins
    return {
        "II": valor_ii,
        "IPI": valor_ipi,
        "PIS": valor_pis,
        "COFINS": valor_cofins,
        "Total_Impostos": total_impostos
    }


# -------------------- Layout Principal --------------------
st.title("Ferramenta de Análise de Cenários de Importação")

if 'module' not in st.session_state:
    st.session_state.module = "Simulador de Cenários"  # Módulo padrão inicial

# Sidebar
st.sidebar.markdown("### Selecione o Módulo:")
if st.sidebar.button("Simulador de Cenários"):
    st.session_state.module = "Simulador de Cenários"
if st.sidebar.button("Gerenciamento"):
    st.session_state.module = "Gerenciamento"
if st.sidebar.button("Histórico de Simulações"):
    st.session_state.module = "Histórico de Simulações"

module_selected = st.session_state.module
st.sidebar.markdown(f"### Módulo Atual: **{module_selected}**")

# Carrega data
data = load_data()

# -------------------- MÓDULO: GERENCIAMENTO --------------------
if module_selected == "Gerenciamento":
    st.header("Gerenciamento de Configurações")
    # Agora vamos ter 4 abas: Filiais, Cenários, Campos de Custo e Produtos
    management_tabs = st.tabs(["Filiais", "Cenários", "Campos de Custo", "Produtos"])

    # 1) Filiais
    with management_tabs[0]:
        st.subheader("Gerenciamento de Filiais")
        new_filial = st.text_input("Nova Filial", key="new_filial_input")
        if st.button("Adicionar Filial"):
            new_filial_stripped = new_filial.strip()
            if new_filial_stripped:
                if new_filial_stripped in data:
                    st.warning("Filial já existe!")
                else:
                    data[new_filial_stripped] = {}
                    save_data(data)
                    st.success("Filial adicionada com sucesso!")
                    st.info("Recarregue a página para ver as alterações.")
            else:
                st.warning("Digite um nome válido para a filial.")

        st.markdown("### Filiais existentes:")
        filiais = [k for k in data.keys() if k != "Produtos"]  # ignora "Produtos" se já existir
        if filiais:
            for filial in filiais:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(filial)
                with col2:
                    if st.button("Excluir", key="delete_filial_" + filial):
                        del data[filial]
                        save_data(data)
                        st.success(f"Filial '{filial}' excluída.")
                        st.info("Recarregue a página para ver as alterações.")
        else:
            st.info("Nenhuma filial cadastrada.")

    # 2) Cenários
    with management_tabs[1]:
        st.subheader("Gerenciamento de Cenários")
        filiais_list = [k for k in data.keys() if k != "Produtos"]
        if not filiais_list:
            st.warning("Nenhuma filial cadastrada. Adicione uma filial na aba Filiais!")
        else:
            filial_select = st.selectbox("Selecione a Filial", filiais_list, key="select_filial_for_scenario")
            scenarios_list = list(data[filial_select].keys())
            st.markdown("### Cenários existentes:")
            if scenarios_list:
                for scenario in scenarios_list:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(scenario)
                    with col2:
                        if st.button("Excluir", key="delete_scenario_" + filial_select + "_" + scenario):
                            del data[filial_select][scenario]
                            save_data(data)
                            st.success(f"Cenário '{scenario}' excluído da filial '{filial_select}'.")
                            st.info("Recarregue a página para ver as alterações.")
            else:
                st.info("Nenhum cenário cadastrado para essa filial.")
            new_scenario = st.text_input("Novo Cenário", key="new_scenario_input")
            if st.button("Adicionar Cenário"):
                new_scenario_stripped = new_scenario.strip()
                if new_scenario_stripped:
                    if new_scenario_stripped in data[filial_select]:
                        st.warning("Cenário já existe para essa filial!")
                    else:
                        data[filial_select][new_scenario_stripped] = {
                            "Frete rodoviário": 0,
                            "ICMS": 0,
                            "IPI": 0,
                            "Taxa MAPA": 0,
                            "Taxas Porto Seco": 0,
                            "Desova EAD": 0,
                            "Taxa cross docking": 0,
                            "Taxa DDC": 0
                        }
                        save_data(data)
                        st.success("Cenário adicionado com sucesso!")
                        st.info("Recarregue a página para ver as alterações.")
                else:
                    st.warning("Digite um nome válido para o cenário.")

    # 3) Campos de Custo
    with management_tabs[2]:
        st.subheader("Gerenciamento de Campos de Custo")
        filiais_list = [k for k in data.keys() if k != "Produtos"]
        if not filiais_list:
            st.warning("Nenhuma filial cadastrada. Adicione uma filial primeiro.")
        else:
            filial_for_field = st.selectbox("Selecione a Filial", filiais_list, key="gerenciamento_filial")
            if not data[filial_for_field]:
                st.info("Nenhum cenário cadastrado para essa filial. Adicione um cenário primeiro.")
            else:
                scenario_for_field = st.selectbox("Selecione o Cenário", list(data[filial_for_field].keys()), key="gerenciamento_cenario")
                scenario_fields = data[filial_for_field][scenario_for_field]
                st.markdown("### Campos Existentes:")
                st.write("**Nome do Campo | Tipo | Valor/Taxa | Base | Ratear Ocupação? | Remover**")

                if scenario_fields:
                    for field in list(scenario_fields.keys()):
                        current = scenario_fields[field]
                        if isinstance(current, dict):
                            current_type = current.get("type", "fixed")
                            current_fixed = float(current.get("value", 0)) if current_type == "fixed" else 0.0
                            current_rate = float(current.get("rate", 0)) if current_type == "percentage" else 0.0
                            current_base = current.get("base", "Valor CIF") if current_type == "percentage" else "Valor CIF"
                            current_rate_occ = bool(current.get("rate_by_occupancy", False))
                        else:
                            current_type = "fixed"
                            current_fixed = float(current)
                            current_rate = 0.0
                            current_base = "Valor CIF"
                            current_rate_occ = False

                        col1, col2, col3, col4, col5, col6 = st.columns([3, 2.5, 2.5, 2.5, 2, 1.5])

                        with col1:
                            st.write(f"**{field}**")

                        with col2:
                            novo_tipo = st.selectbox("Tipo",
                                                     ["fixed", "percentage"],
                                                     index=0 if current_type=="fixed" else 1,
                                                     key=f"tipo_{filial_for_field}_{scenario_for_field}_{field}")

                        novo_config = {}
                        if novo_tipo == "fixed":
                            with col3:
                                novo_valor = st.number_input("Valor Fixo",
                                                             min_value=0.0,
                                                             value=current_fixed,
                                                             key=f"fixo_{filial_for_field}_{scenario_for_field}_{field}")
                            novo_config = {"type": "fixed", "value": novo_valor}
                            col4.write("")
                        else:
                            with col3:
                                nova_taxa = st.number_input("Taxa (%)",
                                                            min_value=0.0,
                                                            value=current_rate * 100,
                                                            step=0.1,
                                                            key=f"taxa_{filial_for_field}_{scenario_for_field}_{field}")
                            with col4:
                                nova_base = st.selectbox("Base",
                                                         ["Valor CIF", "Valor FOB", "Frete Internacional"],
                                                         index=["Valor CIF", "Valor FOB", "Frete Internacional"].index(current_base),
                                                         key=f"base_{filial_for_field}_{scenario_for_field}_{field}")
                            novo_config = {
                                "type": "percentage",
                                "rate": nova_taxa / 100.0,
                                "base": nova_base
                            }

                        with col5:
                            novo_rate_occ = st.checkbox("Ratear?", value=current_rate_occ,
                                                        key=f"rate_occ_{filial_for_field}_{scenario_for_field}_{field}")
                            novo_config["rate_by_occupancy"] = novo_rate_occ

                        if novo_config != current:
                            scenario_fields[field] = novo_config
                            save_data(data)
                            st.success(f"Campo '{field}' atualizado com sucesso!")

                        with col6:
                            if st.button("Remover", key=f"remover_{filial_for_field}_{scenario_for_field}_{field}"):
                                del scenario_fields[field]
                                save_data(data)
                                st.success(f"Campo '{field}' removido com sucesso!")
                                st.stop()
                else:
                    st.info("Nenhum campo definido para este cenário.")

                st.markdown("### Adicionar Novo Campo")
                new_field = st.text_input("Nome do Novo Campo", key="novo_campo")
                if new_field:
                    st.markdown("Defina as opções para o novo campo:")
                    field_type = st.selectbox("Tipo do Campo", ["fixed", "percentage"], key=f"tipo_novo_{new_field}")
                    if field_type == "fixed":
                        field_value = st.number_input("Valor Fixo", min_value=0.0, value=0.0, key=f"valor_novo_{new_field}")
                    else:
                        field_rate = st.number_input("Taxa (%)", min_value=0.0, value=0.0, step=0.1, key=f"taxa_novo_{new_field}")
                        base_option = st.selectbox("Base", ["Valor CIF", "Valor FOB", "Frete Internacional"], key=f"base_novo_{new_field}")
                    rate_occ_new = st.checkbox("Ratear pela Ocupação do Contêiner?", value=False, key=f"rate_occ_new_{new_field}")

                    if st.button("Adicionar Campo", key=f"adicionar_{new_field}"):
                        new_field_stripped = new_field.strip()
                        if new_field_stripped in scenario_fields:
                            st.warning("Campo já existe nesse cenário!")
                        else:
                            if field_type == "fixed":
                                scenario_fields[new_field_stripped] = {
                                    "type": "fixed",
                                    "value": field_value,
                                    "rate_by_occupancy": rate_occ_new
                                }
                            else:
                                scenario_fields[new_field_stripped] = {
                                    "type": "percentage",
                                    "rate": field_rate/100.0,
                                    "base": base_option,
                                    "rate_by_occupancy": rate_occ_new
                                }
                            save_data(data)
                            st.success("Campo adicionado com sucesso!")
                            st.info("Recarregue a página para ver as alterações.")

    # (4) Gerenciamento de Produtos (NCM)
    with management_tabs[3]:
        st.subheader("Gerenciamento de Produtos (NCM)")

        # Se não existir data["Produtos"], criamos
        if "Produtos" not in data:
            data["Produtos"] = {}
            save_data(data)

        produtos = data["Produtos"]  # dict de { ncm: {...} }

        # Listar produtos existentes
        st.markdown("### Produtos Cadastrados:")
        if produtos:
            for ncm_code in list(produtos.keys()):
                prod_info = produtos[ncm_code]
                col1, col2, col3 = st.columns([3, 3, 1])
                with col1:
                    st.write(f"NCM: **{ncm_code}** - {prod_info.get('descricao', '')}")
                with col2:
                    st.write(f"II: {prod_info.get('ii', 0)}% | IPI: {prod_info.get('ipi',0)}% "
                             f"| PIS: {prod_info.get('pis',0)}% | COFINS: {prod_info.get('cofins',0)}%")
                with col3:
                    if st.button("Excluir", key=f"delete_prod_{ncm_code}"):
                        del produtos[ncm_code]
                        save_data(data)
                        st.success(f"Produto NCM {ncm_code} excluído.")
                        st.experimental_rerun()
        else:
            st.info("Nenhum produto cadastrado.")

        st.markdown("### Cadastrar/Editar Produto")
        with st.form("form_produto"):
            ncm_input = st.text_input("NCM do Produto", "")
            desc_input = st.text_input("Descrição do Produto", "")
            ii_input = st.number_input("Alíquota II (%)", min_value=0.0, value=0.0, step=0.1)
            ipi_input = st.number_input("Alíquota IPI (%)", min_value=0.0, value=0.0, step=0.1)
            pis_input = st.number_input("Alíquota PIS (%)", min_value=0.0, value=0.0, step=0.1)
            cofins_input = st.number_input("Alíquota COFINS (%)", min_value=0.0, value=0.0, step=0.1)
            submitted = st.form_submit_button("Salvar Produto")

            if submitted:
                ncm_stripped = ncm_input.strip()
                if ncm_stripped:
                    data["Produtos"][ncm_stripped] = {
                        "descricao": desc_input.strip(),
                        "ii": ii_input,
                        "ipi": ipi_input,
                        "pis": pis_input,
                        "cofins": cofins_input
                    }
                    save_data(data)
                    st.success(f"Produto NCM {ncm_stripped} salvo/atualizado com sucesso!")
                else:
                    st.warning("Digite um código NCM válido.")

# ---------------- MÓDULO: SIMULADOR DE CENÁRIOS ----------------
elif module_selected == "Simulador de Cenários":
    st.header("Simulador de Cenários de Importação")
    if not data:
        st.warning("Nenhuma filial cadastrada. Adicione filiais na aba Gerenciamento.")
    else:
        # Adicionamos também a seleção de Produto (NCM)
        # Precisamos verificar se há produtos cadastrados
        if "Produtos" not in data or not data["Produtos"]:
            st.warning("Nenhum produto (NCM) cadastrado. Vá em Gerenciamento > Produtos para cadastrar.")
        else:
            # Se quiser, a lógica do Simulador Único e Comparação Multifilial fica aqui.
            # Exemplo simples de "Simulador Único" que escolhe filial, cenário e produto:
            filial_select = st.selectbox("Selecione a Filial", [f for f in data.keys() if f != "Produtos"])
            scenario_select = None
            if filial_select:
                if data[filial_select]:
                    scenario_select = st.selectbox("Selecione o Cenário", list(data[filial_select].keys()))
                else:
                    st.warning("Essa filial não possui cenários. Cadastre em Gerenciamento > Cenários.")
            
            produto_list = list(data["Produtos"].keys())
            produto_select = st.selectbox("Selecione o Produto (NCM)", produto_list)

            if filial_select and scenario_select and produto_select:
                # Inputs de simulação
                modo_valor_fob = st.selectbox(
                    "Como deseja informar o Valor FOB?",
                    ["Valor Total", "Unitário × Quantidade"]
                )
                col1, col2 = st.columns(2)
                if modo_valor_fob == "Valor Total":
                    with col1:
                        valor_fob_usd = st.number_input("Valor FOB da Mercadoria (USD)", min_value=0.0, value=0.0)
                        quantidade = 1.0
                        valor_unit_fob_usd = 0.0
                    with col2:
                        frete_internacional_usd = st.number_input("Frete Internacional (USD)", min_value=0.0, value=0.0)
                else:
                    with col1:
                        valor_unit_fob_usd = st.number_input("Valor Unitário FOB (USD/unidade)", min_value=0.0, value=0.0)
                        quantidade = st.number_input("Quantidade", min_value=0.0, value=0.0)
                        frete_internacional_usd = st.number_input("Frete Internacional (USD)", min_value=0.0, value=0.0)
                        valor_fob_usd = valor_unit_fob_usd * quantidade
                    with col2:
                        st.write(f"Valor FOB (USD) calculado: **{valor_fob_usd:,.2f}**")

                percentual_ocupacao_conteiner = st.number_input(
                    "Percentual de Ocupação do Contêiner (%)",
                    min_value=0.0, max_value=100.0, value=100.0
                )
                occupancy_fraction = percentual_ocupacao_conteiner / 100.0

                frete_internacional_usd_rateado = frete_internacional_usd * occupancy_fraction

                taxas_frete_brl = st.number_input("Taxas do Frete (BRL)", min_value=0.0, value=0.0)
                taxas_frete_brl_rateada = taxas_frete_brl * occupancy_fraction

                taxa_cambio = st.number_input("Taxa de Câmbio (USD -> BRL)", min_value=0.0, value=5.0)

                # Calcula Valor CIF (sem taxas_frete_brl no CIF)
                valor_cif_base = (valor_fob_usd + frete_internacional_usd_rateado) * taxa_cambio
                seguro = 0.0015 * (valor_fob_usd * taxa_cambio)
                valor_cif = valor_cif_base + seguro

                st.write(f"Frete Internacional Rateado (USD): {frete_internacional_usd_rateado:,.2f}")
                st.write(f"Taxas do Frete (BRL) Rateadas: {format_brl(taxas_frete_brl_rateada)}")
                st.write(f"Seguro (0,15% do Valor FOB): R$ {format_brl(seguro)}")
                st.write(f"### Valor CIF Calculado (com Seguro): R$ {format_brl(valor_cif)}")

                processo_nome = st.text_input("Nome do Processo", key="nome_processo_input")

                # 1) Monta base_values
                base_values = {
                    "Valor CIF": valor_cif,
                    "Valor FOB": valor_fob_usd,
                    "Frete Internacional": frete_internacional_usd_rateado
                }

                # 2) Calcula custo do cenário
                scenario_data = data[filial_select][scenario_select]
                scenario_cost = calculate_total_cost_extended(scenario_data, base_values, taxa_cambio, occupancy_fraction)
                final_cost_scenario = scenario_cost + taxas_frete_brl_rateada

                # 3) Pega info do produto (NCM) e calcula impostos
                produto_info = data["Produtos"][produto_select]
                impostos_dict = calcular_impostos_produto(produto_info, valor_cif)
                total_impostos_produto = impostos_dict["Total_Impostos"]

                # 4) Soma tudo: custo do cenário + impostos do produto
                custo_total_final = final_cost_scenario + total_impostos_produto

                st.markdown("## Custos do Cenário (Sem Impostos de Produto):")
                st.write(f"Custo do Cenário: R$ {format_brl(final_cost_scenario)}")

                st.markdown("## Impostos do Produto:")
                st.write(f"II: R$ {format_brl(impostos_dict['II'])}")
                st.write(f"IPI: R$ {format_brl(impostos_dict['IPI'])}")
                st.write(f"PIS: R$ {format_brl(impostos_dict['PIS'])}")
                st.write(f"COFINS: R$ {format_brl(impostos_dict['COFINS'])}")
                st.write(f"Total Impostos Produto: R$ {format_brl(total_impostos_produto)}")

                st.markdown(f"## **Custo Total Final:** R$ {format_brl(custo_total_final)}")

                # 5) Botão para salvar no histórico
                if st.button("Salvar Simulação no Histórico"):
                    history = load_history()
                    simulation_record = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "processo_nome": processo_nome,
                        "filial": filial_select,
                        "cenario": scenario_select,
                        "produto_ncm": produto_select,
                        "produto_descricao": produto_info.get("descricao", ""),
                        "valor_unit_fob_usd": valor_unit_fob_usd,
                        "quantidade": float(quantidade),
                        "valor_fob_usd": valor_fob_usd,
                        "frete_internacional_usd": frete_internacional_usd,
                        "percentual_ocupacao_conteiner": percentual_ocupacao_conteiner,
                        "frete_internacional_usd_rateado": frete_internacional_usd_rateado,
                        "taxas_frete_brl": taxas_frete_brl,
                        "taxas_frete_brl_rateada": taxas_frete_brl_rateada,
                        "taxa_cambio": taxa_cambio,
                        "seguro_0_15_valor_fob": float(seguro),
                        "valor_cif": valor_cif,
                        "scenario_cost_no_impostos": final_cost_scenario,
                        "impostos_produto": impostos_dict,
                        "custo_total_final": custo_total_final,
                        "results": {}  # Se quiser armazenar fields do cenário, etc.
                    }
                    # Se quiser, pode armazenar o detail do scenario_data
                    # ex.: simulation_record["results"] = ...
                    history.append(simulation_record)
                    save_history(history)
                    st.success("Simulação salva no histórico com sucesso!")

# ---------------- MÓDULO: HISTÓRICO DE SIMULAÇÕES ----------------
elif module_selected == "Histórico de Simulações":
    st.header("Histórico de Simulações")
    history = load_history()
    if history:
        df_history = pd.DataFrame(history)
        df_history["timestamp"] = pd.to_datetime(df_history["timestamp"], format="%Y-%m-%d %H:%M:%S")
        df_history = df_history.sort_values("timestamp", ascending=False)
        st.markdown("### Registros de Simulação")
        for i, record in df_history.iterrows():
            expander_title = (
                f"{record['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
            )
            if "filial" in record:
                expander_title += f" | Filial: {record['filial']}"
            if "cenario" in record:
                expander_title += f" | Cenário: {record['cenario']}"
            if "produto_ncm" in record:
                expander_title += f" | Produto: {record['produto_ncm']}"
            if "custo_total_final" in record:
                expander_title += f" | Custo Final: R$ {format_brl(record['custo_total_final'])}"

            with st.expander(expander_title):
                st.write(f"**Processo:** {record.get('processo_nome', 'N/A')}")
                st.write(f"**Data/Hora:** {record['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
                st.write(f"**Filial:** {record.get('filial', 'N/A')}")
                st.write(f"**Cenário:** {record.get('cenario', 'N/A')}")
                st.write(f"**Produto (NCM):** {record.get('produto_ncm', 'N/A')} - {record.get('produto_descricao', '')}")
                st.write(f"**Valor CIF:** R$ {format_brl(record.get('valor_cif', 0.0))}")
                st.write(f"**Custo Cenário (Sem Impostos):** R$ {format_brl(record.get('scenario_cost_no_impostos', 0.0))}")
                if "impostos_produto" in record:
                    imp_dict = record["impostos_produto"]
                    st.write(f"**II:** R$ {format_brl(imp_dict.get('II',0))}, "
                             f"**IPI:** R$ {format_brl(imp_dict.get('IPI',0))}, "
                             f"**PIS:** R$ {format_brl(imp_dict.get('PIS',0))}, "
                             f"**COFINS:** R$ {format_brl(imp_dict.get('COFINS',0))}, "
                             f"**Total:** R$ {format_brl(imp_dict.get('Total_Impostos',0))}")
                st.write(f"**Custo Total Final:** R$ {format_brl(record.get('custo_total_final', 0.0))}")

        if st.button("Limpar Histórico"):
            if st.checkbox("Confirme a limpeza do histórico"):
                save_history([])
                st.success("Histórico limpo com sucesso!")
                st.experimental_rerun()
    else:
        st.info("Nenhuma simulação registrada no histórico.")
