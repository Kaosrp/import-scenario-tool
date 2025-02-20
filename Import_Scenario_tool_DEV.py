import streamlit as st
import pandas as pd
import json
import os
import logging
from datetime import datetime
import io
import altair as alt
from typing import Dict, Any, List, Union

# Configuração do logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# -----------------------------
# Constantes dos Arquivos de Configuração
# -----------------------------
FRETE_CONFIG_FILE = "fretes_config.json"
ORIGENS_CONFIG_FILE = "origens_config.json"
DATA_FILE = "cost_config.json"
HISTORY_FILE = "simulation_history.json"
PRODUCT_FILE = "products.json"

# -----------------------------
# Funções Auxiliares e de Persistência com Cache e Tratamento de Erros
# -----------------------------
@st.cache_data(show_spinner=False)
def load_json_file(filename: str) -> Union[Dict[str, Any], List[Any]]:
    """
    Carrega um arquivo JSON e retorna seu conteúdo.
    
    Args:
        filename (str): Nome do arquivo JSON.
    
    Returns:
        dict ou list: Conteúdo do arquivo ou {} / [] em caso de erro.
    """
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                content = f.read().strip()
                if not content:
                    return {} if filename != HISTORY_FILE else []
                return json.loads(content)
        except (json.JSONDecodeError, IOError) as e:
            logging.error("Erro ao carregar %s: %s", filename, e)
            return {} if filename != HISTORY_FILE else []
    return {} if filename != HISTORY_FILE else []

def save_json_file(data: Any, filename: str) -> None:
    """
    Salva os dados em um arquivo JSON.
    
    Args:
        data (Any): Dados a serem salvos.
        filename (str): Nome do arquivo JSON.
    """
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        logging.error("Erro ao salvar %s: %s", filename, e)

# Funções específicas para cada arquivo
def load_frete_config() -> Dict[str, Any]:
    return load_json_file(FRETE_CONFIG_FILE)

def save_frete_config(config: Dict[str, Any]) -> None:
    save_json_file(config, FRETE_CONFIG_FILE)

def load_origens_config() -> Dict[str, Any]:
    return load_json_file(ORIGENS_CONFIG_FILE)

def save_origens_config(config: Dict[str, Any]) -> None:
    save_json_file(config, ORIGENS_CONFIG_FILE)

def load_data() -> Dict[str, Any]:
    return load_json_file(DATA_FILE)

def save_data(data: Dict[str, Any]) -> None:
    save_json_file(data, DATA_FILE)

def load_history() -> List[Any]:
    return load_json_file(HISTORY_FILE)

def save_history(history: List[Any]) -> None:
    save_json_file(history, HISTORY_FILE)

def load_products() -> Dict[str, Any]:
    return load_json_file(PRODUCT_FILE)

def save_products(products: Dict[str, Any]) -> None:
    save_json_file(products, PRODUCT_FILE)

# -----------------------------
# Funções de Cálculo de Custos e Impostos
# -----------------------------
def format_brl(value: Union[float, int]) -> str:
    """
    Formata um número para o padrão monetário BRL.
    """
    try:
        s = "{:,.2f}".format(float(value))
        s = s.replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")
        return s
    except Exception as e:
        logging.error("Erro na formatação do valor: %s", e)
        return str(value)

def calculate_total_cost_extended(
    config: Dict[str, Any],
    base_values: Dict[str, float],
    exchange_rate: float,
    occupancy_fraction: float
) -> float:
    """
    Calcula o custo total de um cenário de importação, somando valores fixos e percentuais.
    
    Args:
        config (dict): Configuração dos campos do cenário.
        base_values (dict): Valores base para os cálculos.
        exchange_rate (float): Taxa de câmbio (USD -> BRL).
        occupancy_fraction (float): Fração de ocupação do container (0 a 1).
    
    Returns:
        float: Custo total calculado.
    """
    extra_cost = 0.0
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
                # Se a base for "Valor FOB" ou "Frete Internacional", aplica o câmbio
                if base.strip().lower() in ["valor fob", "frete internacional"]:
                    base_val *= exchange_rate
                cost_value = base_val * rate
            else:
                cost_value = 0
            if rate_by_occupancy:
                cost_value *= occupancy_fraction
        extra_cost += cost_value
    return base_values.get("Valor CIF", 0) + extra_cost

def calculate_product_taxes(
    product: Dict[str, Any],
    base_values: Dict[str, float],
    exchange_rate: float,
    occupancy_fraction: float
) -> Dict[str, float]:
    """
    Calcula os impostos do produto com base nas alíquotas e bases definidas.
    
    Args:
        product (dict): Dados do produto com as alíquotas de impostos.
        base_values (dict): Valores base para o cálculo.
        exchange_rate (float): Taxa de câmbio (USD -> BRL).
        occupancy_fraction (float): Fração de ocupação do container.
    
    Returns:
        dict: Dicionário com os impostos calculados.
    """
    taxes = {}
    for tax in ["imposto_importacao", "ipi", "pis", "cofins"]:
        tax_info = product.get(tax)
        if tax_info:
            base_name = tax_info.get("base", "")
            base_val = base_values.get(base_name, 0)
            taxes[tax] = base_val * tax_info.get("rate", 0)
        else:
            taxes[tax] = 0.0
    return taxes

# -----------------------------
# Função para Gerar CSV (para exportação)
# -----------------------------
def generate_csv(simulation_record: Dict[str, Any]) -> bytes:
    """
    Gera um CSV a partir dos resultados de uma simulação.
    
    Args:
        simulation_record (dict): Registro da simulação.
    
    Returns:
        bytes: Dados CSV codificados em UTF-8.
    """
    results = simulation_record.get("results", {})
    df = pd.DataFrame(results).T
    df_formatted = df.applymap(lambda x: format_brl(x) if isinstance(x, (int, float)) else x)
    csv_data = df_formatted.to_csv(index=True, sep=";")
    return csv_data.encode("utf-8")

# -----------------------------
# Função Comum para Cálculos de Simulação
# -----------------------------
def compute_simulation_costs(
    config_data: Dict[str, Any],
    filial: str,
    base_values: Dict[str, float],
    exchange_rate: float,
    occupancy_fraction: float,
    additional_freight: float,
    product_tax_values: Dict[str, float]
) -> Dict[str, Any]:
    """
    Realiza os cálculos de custo para uma determinada filial e cenário.
    
    Args:
        config_data (dict): Dados de configuração de cenários para a filial.
        filial (str): Nome da filial.
        base_values (dict): Valores base para o cálculo.
        exchange_rate (float): Taxa de câmbio.
        occupancy_fraction (float): Fração de ocupação do container.
        additional_freight (float): Taxas de frete (BRL) rateadas.
        product_tax_values (dict): Impostos do produto.
    
    Returns:
        dict: Custos calculados para cada cenário.
    """
    costs = {}
    for scenario, conf in config_data.get(filial, {}).items():
        if scenario.lower() == "teste":
            continue
        tem_valor = False
        # Verifica se existe algum valor configurado para o cenário
        for field, field_conf in conf.items():
            if isinstance(field_conf, dict):
                if field_conf.get("type", "fixed") == "fixed" and field_conf.get("value", 0) > 0:
                    tem_valor = True
                elif field_conf.get("type", "percentage") == "percentage":
                    base_name = field_conf.get("base", "")
                    base_val = base_values.get(base_name, 0)
                    if base_name.strip().lower() in ["valor fob", "frete internacional"]:
                        base_val *= exchange_rate
                    if base_val * field_conf.get("rate", 0) > 0:
                        tem_valor = True
            elif field_conf > 0:
                tem_valor = True
        if not tem_valor:
            continue

        scenario_cost = calculate_total_cost_extended(conf, base_values, exchange_rate, occupancy_fraction)
        base_cost = scenario_cost + additional_freight
        final_cost = base_cost + sum(product_tax_values.values())
        scenario_result = {
            "Valor FOB": base_values.get("Valor FOB", 0),
            "Frete internacional": base_values.get("Frete Internacional", 0),
            "Valor CIF com seguro": base_values.get("Valor CIF", 0),
            "Custo final": final_cost
        }
        if base_values.get("Quantidade", 1) > 0:
            scenario_result["Custo Unitário Final"] = final_cost / base_values.get("Quantidade", 1)

        # Adiciona os custos de cada campo
        for field, field_conf in conf.items():
            if isinstance(field_conf, dict):
                field_type = field_conf.get("type", "fixed")
                rate_by_occ = field_conf.get("rate_by_occupancy", False)
                base_name = field_conf.get("base", "")
                if field_type == "fixed":
                    field_val = field_conf.get("value", 0)
                elif field_type == "percentage":
                    rate = field_conf.get("rate", 0)
                    base_val = base_values.get(base_name, 0)
                    if base_name.strip().lower() in ["valor fob", "frete internacional"]:
                        base_val *= exchange_rate
                    field_val = base_val * rate
                else:
                    field_val = 0
                if rate_by_occ:
                    field_val *= occupancy_fraction
                scenario_result[field] = field_val
            else:
                scenario_result[field] = field_conf

        scenario_result["Taxas frete (BRL) rateadas"] = additional_freight
        costs[scenario] = scenario_result

    return costs

# -----------------------------
# Configuração do Logo e Autenticação
# -----------------------------
# Injetar o CSS para posicionar o logo
st.markdown(
    """
    <style>
    .fixed-logo {
      position: fixed;
      top: 20px;
      right: 300px;
      width: 15px;
      z-index: 9999;
    }
    </style>
    <img src="https://www.okubo.com.br/wp-content/uploads/2024/08/Design-sem-nome-7-e1723812969282-200x61.png" class="logo">
    """,
    unsafe_allow_html=True
)

# Dados de usuários (em produção, não utilize senhas em texto plano)
USERS = {
    "admin": {"password": "adminpass", "role": "Administrador"},
    "usuario": {"password": "userpass", "role": "Usuário"},
    "silviara.nobre": {"password": "okubo@2024", "role": "Usuário"},
    "tays.okubo": {"password": "okubo@2024", "role": "Administrador"},
    "matheus.martins": {"password": "okubo@2024", "role": "Administrador"}
}

# Inicializa variáveis no session_state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.module = "Simulador de Cenários"

# -----------------------------
# Tela de Login com st.form
# -----------------------------
if not st.session_state.authenticated:
    st.title("Login")
    with st.form("login_form"):
        username = st.text_input("Usuário", key="login_username")
        password = st.text_input("Senha", type="password", key="login_password")
        submit_login = st.form_submit_button("Entrar")
    if submit_login:
        if username in USERS and password == USERS[username]["password"]:
            st.session_state.authenticated = True
            st.session_state.user_role = USERS[username]["role"]
            st.success("Login efetuado com sucesso!")
            st.experimental_rerun()
        else:
            st.error("Usuário ou senha incorretos!")
    st.stop()

# -----------------------------
# Menu Lateral para Seleção de Módulos
# -----------------------------
st.sidebar.markdown("### Selecione o Módulo:")
if st.sidebar.button("Simulador de Cenários", key="sidebar_simulador"):
    st.session_state.module = "Simulador de Cenários"
if st.sidebar.button("Histórico de Simulações", key="sidebar_historico"):
    st.session_state.module = "Histórico de Simulações"
if st.session_state.user_role == "Administrador":
    if st.sidebar.button("Gerenciamento", key="sidebar_gerenciamento"):
        st.session_state.module = "Gerenciamento"
if st.sidebar.button("Sair", key="sidebar_logout"):
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.experimental_rerun()

module_selected = st.session_state.module
if module_selected == "Gerenciamento" and st.session_state.user_role != "Administrador":
    st.error("Acesso negado. Somente Administradores podem acessar este módulo.")
    st.stop()

# -----------------------------
# Carrega dados de configurações e produtos
# -----------------------------
config_data = load_data()
products = load_products()

# -----------------------------
# MÓDULO: GERENCIAMENTO (Filiais, Cenários, Campos de Custo, Produtos, Origens)
# -----------------------------
if module_selected == "Gerenciamento":
    st.header("Gerenciamento de Configurações")
    management_tabs = st.tabs(["Filiais", "Cenários", "Campos de Custo", "Produtos", "Origens"])
    
    # Aba 1: Gerenciamento de Filiais
    with management_tabs[0]:
        st.subheader("Gerenciamento de Filiais")
        with st.form("form_nova_filial"):
            new_filial = st.text_input("Nova Filial", key="new_filial_input")
            submitted = st.form_submit_button("Adicionar Filial")
        if submitted:
            filial_stripped = new_filial.strip()
            if filial_stripped:
                if filial_stripped in config_data:
                    st.warning("Filial já existe!")
                else:
                    config_data[filial_stripped] = {}
                    save_data(config_data)
                    st.success("Filial adicionada com sucesso!")
                    st.info("Recarregue a página para ver as alterações.")
            else:
                st.warning("Digite um nome válido para a filial.")
        st.markdown("### Filiais existentes:")
        if config_data:
            for filial in list(config_data.keys()):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(filial)
                with col2:
                    if st.button("Excluir", key="delete_filial_" + filial):
                        del config_data[filial]
                        save_data(config_data)
                        st.success(f"Filial '{filial}' excluída.")
                        st.info("Recarregue a página para ver as alterações.")
        else:
            st.info("Nenhuma filial cadastrada.")
    
    # Aba 2: Gerenciamento de Cenários
    with management_tabs[1]:
        st.subheader("Gerenciamento de Cenários")
        if not config_data:
            st.warning("Nenhuma filial cadastrada. Adicione uma filial na aba Filiais!")
        else:
            filial_select = st.selectbox("Selecione a filial", list(config_data.keys()), key="select_filial_for_scenario")
            scenarios_list = list(config_data[filial_select].keys())
            st.markdown("### Cenários existentes:")
            if scenarios_list:
                for scenario in scenarios_list:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(scenario)
                    with col2:
                        if st.button("Excluir", key="delete_scenario_" + filial_select + "_" + scenario):
                            del config_data[filial_select][scenario]
                            save_data(config_data)
                            st.success(f"Cenário '{scenario}' excluído da filial '{filial_select}'.")
                            st.info("Recarregue a página para ver as alterações.")
            else:
                st.info("Nenhum cenário cadastrado para essa filial.")
            with st.form("form_novo_cenario"):
                new_scenario = st.text_input("Novo Cenário", key="new_scenario_input")
                submit_cenario = st.form_submit_button("Adicionar Cenário")
            if submit_cenario:
                scenario_stripped = new_scenario.strip()
                if scenario_stripped:
                    if scenario_stripped in config_data[filial_select]:
                        st.warning("Cenário já existe para essa filial!")
                    else:
                        # Configuração inicial do cenário
                        config_data[filial_select][scenario_stripped] = {
                            "Frete rodoviário": 0,
                            "Marinha Mercante": { 
                                "type": "percentage",
                                "rate": 0.08,  
                                "base": "Frete Internacional",
                                "rate_by_occupancy": False
                            },    
                            "Taxa MAPA": 0,
                            "Taxas Porto Seco": 0,
                            "Desova EAD": 0,
                            "Taxa cross docking": 0,
                            "Taxa DDC": 0
                        }
                        save_data(config_data)
                        st.success("Cenário adicionado com sucesso!")
                        st.info("Recarregue a página para ver as alterações.")
                else:
                    st.warning("Digite um nome válido para o cenário.")
    
    # Aba 3: Gerenciamento de Campos de Custo
    with management_tabs[2]:
        st.subheader("Gerenciamento de Campos de Custo")
        if not config_data:
            st.warning("Nenhuma filial cadastrada. Adicione uma filial primeiro.")
        else:
            filial_for_field = st.selectbox("Selecione a filial", list(config_data.keys()), key="gerenciamento_filial")
            if not config_data[filial_for_field]:
                st.info("Nenhum cenário cadastrado para essa filial. Adicione um cenário primeiro.")
            else:
                scenario_for_field = st.selectbox("Selecione o Cenário", list(config_data[filial_for_field].keys()), key="gerenciamento_cenario")
                scenario_fields = config_data[filial_for_field][scenario_for_field]
                st.markdown("### Campos existentes:")
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
                        col1, col2, col3, col4, col5, col6 = st.columns([2.2, 2.5, 2.5, 2.5, 2, 2])
                        with col1:
                            st.write(f"**{field}**")
                        with col2:
                            novo_tipo = st.selectbox("Tipo", ["fixed", "percentage"],
                                                       index=0 if current_type=="fixed" else 1,
                                                       key=f"tipo_{filial_for_field}_{scenario_for_field}_{field}")
                        novo_config = {}
                        if novo_tipo == "fixed":
                            with col3:
                                novo_valor = st.number_input("Valor Fixo", min_value=0.0,
                                                             value=current_fixed,
                                                             key=f"fixo_{filial_for_field}_{scenario_for_field}_{field}")
                            novo_config = {"type": "fixed", "value": novo_valor, "rate_by_occupancy": current_rate_occ}
                            col4.write("")
                        else:
                            with col3:
                                nova_taxa = st.number_input("Taxa (%)", min_value=0.0,
                                                            value=current_rate * 100,
                                                            step=0.1,
                                                            key=f"taxa_{filial_for_field}_{scenario_for_field}_{field}")
                            with col4:
                                nova_base = st.selectbox("Base", ["Valor CIF", "Valor FOB", "Frete Internacional"],
                                                         index=["Valor CIF", "Valor FOB", "Frete Internacional"].index(current_base),
                                                         key=f"base_{filial_for_field}_{scenario_for_field}_{field}")
                            novo_config = {"type": "percentage", "rate": nova_taxa / 100.0, "base": nova_base}
                        with col5:
                            novo_rate_occ = st.checkbox("Ratear?", value=current_rate_occ,
                                                        key=f"rate_occ_{filial_for_field}_{scenario_for_field}_{field}")
                            novo_config["rate_by_occupancy"] = novo_rate_occ
                        if novo_config != current:
                            scenario_fields[field] = novo_config
                            save_data(config_data)
                            st.success(f"Campo '{field}' atualizado com sucesso!")
                        with col6:
                            if st.button("Remover", key=f"remover_{filial_for_field}_{scenario_for_field}_{field}"):
                                del scenario_fields[field]
                                save_data(config_data)
                                st.success(f"Campo '{field}' removido com sucesso!")
                                st.stop()
                else:
                    st.info("Nenhum campo definido para este cenário.")
                
                st.markdown("### Adicionar Novo Campo")
                # Atualização: formulário corrigido com submit button fixo
                with st.form("form_novo_campo"):
                    new_field = st.text_input("Nome do Novo Campo", key="novo_campo")
                    st.markdown("Defina as opções para o novo campo:")
                    field_type = st.selectbox("Tipo do Campo", ["fixed", "percentage"], key="tipo_novo")
                    if field_type == "fixed":
                        field_value = st.number_input("Valor Fixo", min_value=0.0, value=0.0, key="valor_novo")
                    else:
                        field_rate = st.number_input("Taxa (%)", min_value=0.0, value=0.0, step=0.1, key="taxa_novo")
                        base_option = st.selectbox("Base", ["Valor CIF", "Valor FOB", "Frete Internacional"], key="base_novo")
                    rate_occ_new = st.checkbox("Ratear pela ocupação do contêiner?", value=False, key="rate_occ_new")
                    submit_novo_campo = st.form_submit_button("Adicionar Campo")
                if submit_novo_campo:
                    new_field_stripped = new_field.strip()
                    if not new_field_stripped:
                        st.warning("Digite um nome válido para o novo campo.")
                    elif new_field_stripped in scenario_fields:
                        st.warning("Campo já existe nesse cenário!")
                    else:
                        if field_type == "fixed":
                            scenario_fields[new_field_stripped] = {"type": "fixed", "value": field_value, "rate_by_occupancy": rate_occ_new}
                        else:
                            scenario_fields[new_field_stripped] = {"type": "percentage", "rate": field_rate / 100.0, "base": base_option, "rate_by_occupancy": rate_occ_new}
                        save_data(config_data)
                        st.success("Campo adicionado com sucesso!")
                        st.info("Recarregue a página para ver as alterações.")
                        
    # Aba 4: Gerenciamento de Produtos (NCM)
    with management_tabs[3]:
        st.subheader("Gerenciamento de Produtos (NCM)")
        st.write("Cadastre produtos com suas alíquotas de Imposto de Importação (II), IPI, PIS e Cofins.")
        with st.form("form_produto"):
            edit_mode = st.session_state.get("edit_product", None)
            if edit_mode:
                st.subheader(f"Editar Produto (NCM: {edit_mode})")
                prod_data = products.get(edit_mode, {})
                if st.button("Cancelar Edição"):
                    del st.session_state.edit_product
            else:
                st.subheader("Adicionar Novo Produto")
                prod_data = {}
            ncm_input = st.text_input("NCM", value=edit_mode if edit_mode else "", key="ncm_input")
            descricao = st.text_input("Descrição", value=prod_data.get("descricao", ""), key="descricao_input")
            st.markdown("#### Alíquotas de Impostos (valores em %)")
            st.markdown("**Imposto de Importação (II):**")
            col_ii = st.columns(2)
            with col_ii[0]:
                ii_rate = st.number_input("Alíquota (%)", min_value=0.0,
                                            value=prod_data.get("imposto_importacao", {}).get("rate", 0.0) * 100,
                                            step=0.1, key="ii_rate")
            with col_ii[1]:
                ii_base = st.selectbox("Base", ["Valor CIF", "Valor FOB", "Frete Internacional"],
                                       index=["Valor CIF", "Valor FOB", "Frete Internacional"].index(
                                           prod_data.get("imposto_importacao", {}).get("base", "Valor CIF")
                                       ), key="ii_base")
            st.markdown("**IPI:**")
            col_ipi = st.columns(2)
            with col_ipi[0]:
                ipi_rate = st.number_input("Alíquota (%)", min_value=0.0,
                                             value=prod_data.get("ipi", {}).get("rate", 0.0) * 100,
                                             step=0.1, key="ipi_rate")
            with col_ipi[1]:
                ipi_base = st.selectbox("Base", ["Valor CIF", "Valor FOB", "Frete Internacional"],
                                        index=["Valor CIF", "Valor FOB", "Frete Internacional"].index(
                                            prod_data.get("ipi", {}).get("base", "Valor CIF")
                                        ), key="ipi_base")
            st.markdown("**PIS:**")
            col_pis = st.columns(2)
            with col_pis[0]:
                pis_rate = st.number_input("Alíquota (%)", min_value=0.0,
                                             value=prod_data.get("pis", {}).get("rate", 0.0) * 100,
                                             step=0.1, key="pis_rate")
            with col_pis[1]:
                pis_base = st.selectbox("Base", ["Valor CIF", "Valor FOB", "Frete Internacional"],
                                        index=["Valor CIF", "Valor FOB", "Frete Internacional"].index(
                                            prod_data.get("pis", {}).get("base", "Valor CIF")
                                        ), key="pis_base")
            st.markdown("**Cofins:**")
            col_cofins = st.columns(2)
            with col_cofins[0]:
                cofins_rate = st.number_input("Alíquota (%)", min_value=0.0,
                                               value=prod_data.get("cofins", {}).get("rate", 0.0) * 100,
                                               step=0.1, key="cofins_rate")
            with col_cofins[1]:
                cofins_base = st.selectbox("Base", ["Valor CIF", "Valor FOB", "Frete Internacional"],
                                           index=["Valor CIF", "Valor FOB", "Frete Internacional"].index(
                                               prod_data.get("cofins", {}).get("base", "Valor CIF")
                                           ), key="cofins_base")
            submit_produto = st.form_submit_button("Salvar Produto")
        if submit_produto:
            if not ncm_input.strip():
                st.warning("Informe o NCM.")
            else:
                product_record = {
                    "descricao": descricao,
                    "imposto_importacao": {"rate": ii_rate / 100.0, "base": ii_base},
                    "ipi": {"rate": ipi_rate / 100.0, "base": ipi_base},
                    "pis": {"rate": pis_rate / 100.0, "base": pis_base},
                    "cofins": {"rate": cofins_rate / 100.0, "base": cofins_base}
                }
                products[ncm_input.strip()] = product_record
                save_products(products)
                st.success("Produto salvo com sucesso!")
                st.balloons()
                if "edit_product" in st.session_state:
                    del st.session_state.edit_product
        st.markdown("---")
        st.subheader("Produtos Cadastrados")
        search_query = st.text_input("Buscar Produto", key="search_produto")
        if products:
            filtered_products = {ncm: prod for ncm, prod in products.items() if
                                 search_query.lower() in ncm.lower() or search_query.lower() in prod.get("descricao", "").lower()} \
                if search_query else products
            if filtered_products:
                for ncm, prod in filtered_products.items():
                    col1, col2 = st.columns([7, 3])
                    with col1:
                        product_html = f"""
                        <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 15px; background: #fff;
                        box-shadow: 2px 2px 5px rgba(0,0,0,0.1); margin-bottom: 15px;">
                            <h4 style="margin-bottom: 10px; color: #333;">NCM: {ncm}</h4>
                            <p style="margin: 0;"><strong>Descrição:</strong> {prod.get('descricao', 'N/A')}</p>
                            <p style="margin: 0;"><strong>II:</strong> {prod.get('imposto_importacao', {}).get('rate', 0)*100:.2f}% (Base: {prod.get('imposto_importacao', {}).get('base', 'N/A')})</p>
                            <p style="margin: 0;"><strong>IPI:</strong> {prod.get('ipi', {}).get('rate', 0)*100:.2f}% (Base: {prod.get('ipi', {}).get('base', 'N/A')})</p>
                            <p style="margin: 0;"><strong>Pis:</strong> {prod.get('pis', {}).get('rate', 0)*100:.2f}% (Base: {prod.get('pis', {}).get('base', 'N/A')})</p>
                            <p style="margin: 0;"><strong>Cofins:</strong> {prod.get('cofins', {}).get('rate', 0)*100:.2f}% (Base: {prod.get('cofins', {}).get('base', 'N/A')})</p>
                        </div>
                        """
                        st.markdown(product_html, unsafe_allow_html=True)
                    with col2:
                        if st.button("Editar", key=f"edit_{ncm}"):
                            st.session_state.edit_product = ncm
                        if st.button("Excluir", key=f"del_{ncm}"):
                            del products[ncm]
                            save_products(products)
                            st.success(f"Produto {ncm} excluído!")
                            st.experimental_rerun()
            else:
                st.info("Nenhum produto encontrado para a busca.")
        else:
            st.info("Nenhum produto cadastrado.")
    
    # Aba 5: Gerenciamento de Origens
    with management_tabs[4]:
        st.subheader("Gerenciamento de Origens")
        origens_config = load_origens_config()
        with st.form("form_nova_origem"):
            nova_origem = st.text_input("Nova Origem", key="nova_origem")
            frete_internacional = st.number_input("Frete Internacional (USD)", min_value=0.0, value=0.0, key="frete_internacional_nova")
            taxas_frete = st.number_input("Taxas de Frete (BRL)", min_value=0.0, value=0.0, key="taxas_frete_nova")
            submit_origem = st.form_submit_button("Adicionar Origem")
        if submit_origem:
            if nova_origem.strip():
                if nova_origem in origens_config:
                    st.warning("Origem já existe!")
                else:
                    origens_config[nova_origem.strip()] = {
                        "frete_internacional_usd": frete_internacional,
                        "taxas_frete_brl": taxas_frete
                    }
                    save_origens_config(origens_config)
                    st.success("Origem adicionada com sucesso!")
            else:
                st.warning("Informe um nome válido para a origem.")
        st.markdown("### Origens Configuradas:")
        for origem, values in origens_config.items():
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
            with col1:
                st.write(origem)
            with col2:
                st.write(f"Frete Internacional: USD {values['frete_internacional_usd']}")
            with col3:
                st.write(f"Taxas de Frete: BRL {values['taxas_frete_brl']}")
            with col4:
                if st.button("Editar", key=f"editar_{origem}"):
                    st.session_state.edit_origem = origem
            with col5:
                if st.button("Excluir", key=f"excluir_{origem}"):
                    del origens_config[origem]
                    save_origens_config(origens_config)
                    st.success(f"Origem '{origem}' excluída!")
        if "edit_origem" in st.session_state:
            origem_to_edit = st.session_state.edit_origem
            st.markdown(f"### Editar Origem: {origem_to_edit}")
            current_values = origens_config.get(origem_to_edit, {"frete_internacional_usd": 0.0, "taxas_frete_brl": 0.0})
            new_frete_internacional = st.number_input("Frete Internacional (USD)", min_value=0.0,
                                                        value=current_values["frete_internacional_usd"],
                                                        key="edit_frete_internacional")
            new_taxas_frete = st.number_input("Taxas de Frete (BRL)", min_value=0.0,
                                              value=current_values["taxas_frete_brl"],
                                              key="edit_taxas_frete")
            if st.button("Salvar Alterações", key="salvar_edicao_origem"):
                origens_config[origem_to_edit] = {
                    "frete_internacional_usd": new_frete_internacional,
                    "taxas_frete_brl": new_taxas_frete
                }
                save_origens_config(origens_config)
                st.success("Origem atualizada com sucesso!")
                del st.session_state.edit_origem

# -----------------------------
# MÓDULO: SIMULADOR DE CENÁRIOS
# -----------------------------
elif module_selected == "Simulador de Cenários":
    st.header("QAS - Simulador de Cenários de Importação")
    sim_mode = st.radio("Escolha o modo de Simulação", ["Simulador único", "Comparação multifilial"], index=0)
    processo_nome = st.text_input("Nome do processo", key="nome_processo_input")
    
    # Seleção de produto
    if products:
        options = []
        mapping = {}
        for ncm, prod in products.items():
            label = f"{ncm} - {prod.get('descricao', 'Sem descrição')}"
            options.append(label)
            mapping[label] = ncm
        selected_label = st.selectbox("Selecione o produto (NCM)", options)
        product_key = mapping[selected_label]
        product = products[product_key]
    else:
        st.info("Nenhum produto cadastrado. Cadastre um produto em 'Produtos'.")
        product = None
        
    if sim_mode == "Simulador único":
        if not config_data:
            st.warning("Nenhuma filial cadastrada. Adicione filiais na aba Gerenciamento.")
        else:
            filial_selected = st.selectbox("Selecione a filial", list(config_data.keys()))
            with st.form("form_simulacao_unica"):
                modo_valor_fob = st.selectbox("Como deseja informar o Valor FOB?", ["Valor total", "Unitário × Quantidade"], key="modo_valor_fob")
                col1, col2 = st.columns(2)
                if modo_valor_fob == "Valor total":
                    with col1:
                        valor_fob_usd = st.number_input("Valor FOB da mercadoria (USD)", min_value=0.0, value=0.0, key="valor_fob_usd")
                        quantidade = 1.0
                        valor_unit_fob_usd = 0.0
                    with col2:
                        st.write("Usando frete internacional configurado via origem")
                else:
                    with col1:
                        valor_unit_fob_usd = st.number_input("Valor unitário FOB (USD/unidade)", min_value=0.0, value=0.0, key="valor_unit_fob_usd")
                        quantidade = st.number_input("Quantidade", min_value=0.0, value=0.0, key="quantidade")
                        valor_fob_usd = valor_unit_fob_usd * quantidade
                    with col2:
                        st.write(f"Valor FOB (USD) calculado: **{valor_fob_usd:,.2f}**")
                
                origens_config = load_origens_config()
                if origens_config:
                    origem_selecionada = st.selectbox("Selecione a origem do material", list(origens_config.keys()), key="origem_selecionada")
                    frete_internacional_usd = origens_config[origem_selecionada]["frete_internacional_usd"]
                    taxas_frete_brl = origens_config[origem_selecionada]["taxas_frete_brl"]
                else:
                    st.info("Nenhuma origem configurada. Por favor, solicite ao administrador.")
                    frete_internacional_usd = 0.0
                    taxas_frete_brl = 0.0
                
                percentual_ocupacao = st.number_input("Percentual de ocupação do contêiner (%)", min_value=0.0, max_value=100.0, value=100.0, key="percentual_ocupacao")
                occupancy_fraction = percentual_ocupacao / 100.0
                frete_internacional_rateado = frete_internacional_usd * occupancy_fraction
                taxas_frete_rateada = taxas_frete_brl * occupancy_fraction
                taxa_cambio = st.number_input("Taxa de Câmbio (USD -> BRL)", min_value=0.0, value=5.0, key="taxa_cambio")
                valor_cif_base = (valor_fob_usd + frete_internacional_rateado) * taxa_cambio
                seguro = 0.0015 * (valor_fob_usd * taxa_cambio)
                valor_cif = valor_cif_base + seguro
                base_values = {
                    "Valor CIF": valor_cif,
                    "Valor FOB": valor_fob_usd,
                    "Frete Internacional": frete_internacional_rateado,
                    "Quantidade": quantidade
                }
                submit_sim_unica = st.form_submit_button("Calcular Simulação")
            
            if submit_sim_unica:
                if product:
                    product_taxes = calculate_product_taxes(product, base_values, taxa_cambio, occupancy_fraction)
                else:
                    product_taxes = {"imposto_importacao": 0, "ipi": 0, "pis": 0, "cofins": 0}
                costs = compute_simulation_costs(config_data, filial_selected, base_values, taxa_cambio, occupancy_fraction, taxas_frete_rateada, product_taxes)
                if costs:
                    df = pd.DataFrame(costs).T.sort_values(by="Custo final")
                    df_display = df.applymap(lambda x: format_brl(x) if isinstance(x, (int, float)) else x)
                    st.write("### Comparação por filial única")
                    st.dataframe(df_display)
                    best_scenario = df.index[0]
                    best_cost = df.iloc[0]['Custo final']
                    st.write(f"O melhor cenário para {filial_selected} é **{best_scenario}** com custo final de **R$ {format_brl(best_cost)}**.")
                    
                    df_reset = df.reset_index().rename(columns={"index": "Cenário"})
                    chart = alt.Chart(df_reset).mark_bar().encode(
                        x=alt.X("Cenário:N", sort=None),
                        y=alt.Y("Custo final:Q", title="Custo Final (BRL)"),
                        tooltip=["Cenário", "Custo final"]
                    ).properties(title="Comparação de Custos por Cenário")
                    st.altair_chart(chart, use_container_width=True)
                    
                    if st.button("Salvar Simulação no Histórico"):
                        history = load_history()
                        simulation_record = {
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "processo_nome": processo_nome,
                            "filial": filial_selected,
                            "modo_valor_fob": modo_valor_fob,
                            "valor_unit_fob_usd": valor_unit_fob_usd,
                            "quantidade": float(quantidade),
                            "valor_fob_usd": valor_fob_usd,
                            "frete_internacional_usd": frete_internacional_usd,
                            "percentual_ocupacao": percentual_ocupacao,
                            "frete_internacional_rateado": frete_internacional_rateado,
                            "taxas_frete_brl": taxas_frete_brl,
                            "taxas_frete_rateada": taxas_frete_rateada,
                            "taxa_cambio": taxa_cambio,
                            "seguro": float(seguro),
                            "valor_cif": valor_cif,
                            "best_scenario": best_scenario,
                            "best_cost": best_cost,
                            "results": costs,
                            "multi_comparison": False,
                            "final_cost_com_impostos": best_cost,
                            "produto": {"ncm": product_key, "descricao": product.get("descricao", "")} if product else {}
                        }
                        if quantidade > 0:
                            simulation_record["custo_unitario_melhor"] = best_cost / quantidade
                        history.append(simulation_record)
                        save_history(history)
                        st.success("Simulação salva no histórico com sucesso!")
                else:
                    st.warning("Nenhuma configuração encontrada para a filial selecionada.")
                    
    else:
        st.subheader("Comparação multifilial")
        if not config_data:
            st.warning("Nenhuma filial cadastrada. Adicione filiais na aba Gerenciamento.")
        else:
            filiais_multi = st.multiselect("Selecione as Filiais para comparar", list(config_data.keys()))
            if filiais_multi:
                with st.form("form_simulacao_multi"):
                    modo_valor_fob = st.selectbox("Como deseja informar o Valor FOB?", ["Valor total", "Unitário × Quantidade"], key="modo_valor_fob_multi")
                    col1, col2 = st.columns(2)
                    if modo_valor_fob == "Valor total":
                        with col1:
                            valor_fob_usd = st.number_input("Valor FOB da mercadoria (USD)", min_value=0.0, value=0.0, key="valor_fob_usd_multi")
                            quantidade = 1.0
                            valor_unit_fob_usd = 0.0
                        with col2:
                            st.write("Usando frete internacional configurado via origem")
                    else:
                        with col1:
                            valor_unit_fob_usd = st.number_input("Valor Unitário FOB (USD/unidade)", min_value=0.0, value=0.0, key="valor_unit_fob_usd_multi")
                            quantidade = st.number_input("Quantidade", min_value=0.0, value=0.0, key="quantidade_multi")
                            valor_fob_usd = valor_unit_fob_usd * quantidade
                        with col2:
                            st.write(f"Valor FOB (USD) calculado: **{valor_fob_usd:,.2f}**")
                    
                    origens_config = load_origens_config()
                    if origens_config:
                        origem_selecionada = st.selectbox("Selecione a Origem do Material", list(origens_config.keys()), key="origem_selecionada_multi")
                        frete_internacional_usd = origens_config[origem_selecionada]["frete_internacional_usd"]
                        taxas_frete_brl = origens_config[origem_selecionada]["taxas_frete_brl"]
                    else:
                        st.info("Nenhuma origem configurada. Por favor, solicite ao administrador.")
                        frete_internacional_usd = 0.0
                        taxas_frete_brl = 0.0
                    
                    percentual_ocupacao = st.number_input("Percentual de Ocupação do Contêiner (%)", min_value=0.0, max_value=100.0, value=100.0, key="percentual_ocupacao_multi")
                    occupancy_fraction = percentual_ocupacao / 100.0
                    frete_internacional_rateado = frete_internacional_usd * occupancy_fraction
                    taxas_frete_rateada = taxas_frete_brl * occupancy_fraction
                    taxa_cambio = st.number_input("Taxa de Câmbio (USD -> BRL)", min_value=0.0, value=5.0, key="taxa_cambio_multi")
                    valor_cif_base = (valor_fob_usd + frete_internacional_rateado) * taxa_cambio
                    seguro = 0.0015 * (valor_fob_usd * taxa_cambio)
                    valor_cif = valor_cif_base + seguro
                    base_values = {
                        "Valor CIF": valor_cif,
                        "Valor FOB": valor_fob_usd,
                        "Frete Internacional": frete_internacional_rateado,
                        "Quantidade": quantidade
                    }
                    submit_sim_multi = st.form_submit_button("Calcular Comparação")
                if submit_sim_multi:
                    if product:
                        product_taxes = calculate_product_taxes(product, base_values, taxa_cambio, occupancy_fraction)
                    else:
                        product_taxes = {"imposto_importacao": 0, "ipi": 0, "pis": 0, "cofins": 0}
                    multi_costs = {}
                    for filial in filiais_multi:
                        if filial not in config_data:
                            continue
                        filial_costs = compute_simulation_costs(config_data, filial, base_values, taxa_cambio, occupancy_fraction, taxas_frete_rateada, product_taxes)
                        for scenario, result in filial_costs.items():
                            key = (filial, scenario)
                            result["Filial"] = filial
                            result["Cenário"] = scenario
                            multi_costs[key] = result
                    if multi_costs:
                        df_multi = pd.DataFrame(multi_costs).T.sort_values(by="Custo final")
                        df_display = df_multi.applymap(lambda x: format_brl(x) if isinstance(x, (int, float)) else x)
                        st.write("### Comparação global (multifilial)")
                        st.dataframe(df_display)
                        best_row = df_multi.iloc[0]
                        best_filial = best_row["Filial"]
                        best_scenario = best_row["Cenário"]
                        best_cost = best_row["Custo final"]
                        st.write(f"O melhor cenário geral é **{best_scenario}** da filial **{best_filial}** com custo final de **R$ {format_brl(best_cost)}**.")
                        if st.button("Salvar comparação no histórico"):
                            history = load_history()
                            simulation_record = {
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "processo_nome": processo_nome,
                                "multi_comparison": True,
                                "filiais_multi": filiais_multi,
                                "modo_valor_fob": modo_valor_fob,
                                "valor_unit_fob_usd": valor_unit_fob_usd,
                                "quantidade": float(quantidade),
                                "valor_fob_usd": valor_fob_usd,
                                "frete_internacional_usd": frete_internacional_usd,
                                "percentual_ocupacao": percentual_ocupacao,
                                "frete_internacional_rateado": frete_internacional_rateado,
                                "taxas_frete_brl": taxas_frete_brl,
                                "taxas_frete_rateada": taxas_frete_rateada,
                                "taxa_cambio": taxa_cambio,
                                "seguro": float(seguro),
                                "valor_cif": valor_cif,
                                "best_filial": best_filial,
                                "best_scenario": best_scenario,
                                "best_cost": best_cost,
                                "results": {},
                                "final_cost_com_impostos": best_cost,
                                "produto": {"ncm": product_key, "descricao": product.get("descricao", "")} if product else {}
                            }
                            df_multi.index = df_multi.index.map(lambda x: " | ".join(map(str, x)) if isinstance(x, tuple) else str(x))
                            simulation_record["results"] = df_multi.to_dict(orient="index")
                            history.append(simulation_record)
                            save_history(history)
                            st.success("Comparação multifilial salva no histórico com sucesso!")
                    else:
                        st.warning("Nenhuma configuração encontrada para as filiais selecionadas.")
            else:
                st.info("Selecione pelo menos uma filial para comparar.")

# -----------------------------
# MÓDULO: HISTÓRICO DE SIMULAÇÕES
# -----------------------------
elif module_selected == "Histórico de Simulações":
    st.header("Histórico de Simulações")
    history = load_history()
    if history:
        sorted_history = sorted(history, key=lambda r: datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S"), reverse=True)
        st.markdown("### Registros de Simulação")
        for record in sorted_history:
            expander_title = f"{record['timestamp']}"
            if "best_scenario" in record:
                expander_title += f" | Melhor: {record['best_scenario']}"
            if "best_cost" in record:
                expander_title += f" | Custo final: R$ {format_brl(record['best_cost'])}"
            if record.get("multi_comparison", False):
                expander_title += " (Comparação multifilial)"
            else:
                expander_title += f" | Filial: {record.get('filial', 'N/A')}"
            with st.expander(expander_title):
                st.write(f"**Processo:** {record.get('processo_nome', 'N/A')}")
                st.write(f"**Data/Hora:** {record['timestamp']}")
                if record.get("multi_comparison", False):
                    filiais = record.get("filiais_multi", [])
                    if filiais:
                        st.write("**Filiais Selecionadas:** " + ", ".join(filiais))
                    st.write("**Melhor filial:**", record.get("best_filial", "N/A"))
                    st.write("**Melhor cenário:**", record.get("best_scenario", "N/A"))
                    st.write("**Custo final:** R$", format_brl(record.get("best_cost", 0.0)))
                    st.write("**Valor CIF com seguro:** R$", format_brl(record.get("valor_cif", 0.0)))
                    
                    results_dict = record.get("results", {})
                    if results_dict:
                        results_df = pd.DataFrame.from_dict(results_dict, orient="index")
                        results_df_display = results_df.applymap(lambda x: format_brl(x) if isinstance(x, (int, float)) else x)
                        st.dataframe(results_df_display)
                
                else:
                    st.write(f"**Filial:** {record.get('filial', 'N/A')}")
                    st.write(f"**Melhor cenário:** {record.get('best_scenario', 'N/A')}")
                    st.write(f"**Custo final:** R$ {format_brl(record.get('best_cost', 0.0))}")
                    st.write("**Valor FOB:** R$ ", format_brl(record.get("valor_fob_usd", 0.0)))
                    st.write("**Valor CIF com seguro:** R$ ", format_brl(record.get("valor_cif", 0.0)))
                    results_dict = record.get("results", {})
                    if results_dict:
                        results_df = pd.DataFrame(results_dict).T
                        results_df_display = results_df.applymap(lambda x: format_brl(x) if isinstance(x, (int, float)) else x)
                        st.dataframe(results_df_display)
                
                if st.button("Excluir este registro", key=f"delete_{record['timestamp']}"):
                    sorted_history.remove(record)
                    save_history(sorted_history)
                    st.success("Registro excluído com sucesso!")
    else:
        st.info("Nenhuma simulação registrada no histórico.")
