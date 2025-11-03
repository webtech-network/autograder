import os
import sys
import json
from dotenv import load_dotenv

# --- Configuração de Importação ---
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Tenta importar o driver
try:
    # ATUALIZADO: Importando sua classe 'Driver'
    from autograder.core.utils.upstash_driver import Driver
except ImportError as e:
    print(f"❌ Erro de Importação: {e}")
    print("Verifique se o nome da classe é 'Driver' e a localização está correta.")
    print("Localização esperada: /autograder/core/utils/upstash_driver.py")
    sys.exit(1)
except ModuleNotFoundError:
    print("❌ Erro: Módulo 'autograder' não encontrado.")
    print("Certifique-se de que você está executando este script da raiz do seu projeto.")
    sys.exit(1)

# Carrega variáveis de ambiente (REDIS_URL, REDIS_TOKEN) do arquivo .env
load_dotenv()

# --- Constantes de Teste ---
TEST_USERNAME = "playroom_user_hash"
TEST_SCORE = 99.5
TEST_TOKEN = "playroom_token_hash"
TEST_QUOTA = 3

# Chaves exatas que serão usadas no Redis
USER_KEY = f"user:{TEST_USERNAME}"
TOKEN_KEY = f"token:{TEST_TOKEN}"
# A SCORE_KEY separada não é mais necessária, pois o score vive dentro do USER_KEY


def cleanup(driver_instance):
    """Apaga todas as chaves de teste para garantir um ambiente limpo."""
    print("\n--- 🧹 Limpando dados de teste... ---")
    try:
        # ATUALIZADO: Chaves de teste
        keys_to_delete = [USER_KEY, TOKEN_KEY]
        deleted_count = driver_instance.redis.delete(*keys_to_delete)
        print(f"Foram apagadas {deleted_count} chaves de teste.")
    except Exception as e:
        print(f"❌ Erro na limpeza: {e}")

def main():
    """Função principal para executar os testes."""
    print("--- 🏁 Iniciando o Redis Playroom ---")

    try:
        # 1. Inicializa o Driver
        # ATUALIZADO: Usando seu método .create() e as variáveis do .env
        print("Conectando ao Upstash Redis usando .env...")
        driver = Driver.create(
            redis_token=os.getenv("REDIS_TOKEN"),
            redis_url=os.getenv("REDIS_URL")
        )
        driver.redis.ping() # Testa a conexão
        print("✅ Conexão com Redis estabelecida pelo driver.")
    except Exception as e:
        print(f"❌ ERRO CRÍTICO: Falha ao inicializar ou conectar o driver: {e}")
        print("Verifique seu arquivo .env e se as variáveis REDIS_URL/TOKEN estão corretas.")
        return # Encerra o script

    # Limpa dados de testes anteriores antes de começar
    cleanup(driver)

    # --- 🧪 Teste 1: Funções de Usuário (Modelo HASH) ---
    print("\n--- 🧪 Teste 1: Funções de Usuário (Modelo HASH) ---")
    try:
        # 1.1 user_exists (deve ser Falso)
        print(f"Verificando se '{TEST_USERNAME}' existe (deve ser Falso)...")
        exists = driver.user_exists(TEST_USERNAME)
        print(f"Resultado: {exists}" + (" ✅" if not exists else " ❌"))

        # 1.2 create_user
        print(f"Criando usuário '{TEST_USERNAME}' (com score inicial -1.0)...")
        driver.create_user(TEST_USERNAME)

        # Verificação direta no Redis (para confirmar o modelo de dados)
        user_data_hash = driver.redis.hgetall(USER_KEY)
        print(f"Verificação direta (Hash): {user_data_hash}")
        assert user_data_hash is not None
        assert user_data_hash.get("username") == TEST_USERNAME
        assert float(user_data_hash.get("score")) == -1.0
        print("✅ Usuário criado corretamente (modelo HASH).")

        # 1.3 user_exists (deve ser Verdadeiro)
        print(f"Verificando se '{TEST_USERNAME}' existe (deve ser Verdadeiro)...")
        exists = driver.user_exists(TEST_USERNAME)
        print(f"Resultado: {exists}" + (" ✅" if exists else " ❌"))

        # 1.4 set_score (usando a nova função corrigida)
        print(f"Definindo score '{TEST_SCORE}' para o usuário...")
        driver.set_score(TEST_USERNAME, TEST_SCORE)

        # Verificação direta no Redis
        score_data = driver.redis.hget(USER_KEY, "score")
        print(f"Verificação direta (Score): {score_data}")
        assert score_data is not None
        assert float(score_data) == TEST_SCORE
        print("✅ Score definido corretamente (campo 'score' no HASH).")

    except Exception as e:
        print(f"❌ ERRO no Teste 1: {e}")

    # --- 🧪 Teste 2: Funções de Token (Modelo HASH) ---
    print("\n--- 🧪 Teste 2: Funções de Token (Modelo HASH) ---")
    try:
        # 2.1 token_exists (deve ser Falso)
        print(f"Verificando se o token '{TEST_TOKEN}' existe (deve ser Falso)...")
        exists = driver.token_exists(TEST_TOKEN)
        print(f"Resultado: {exists}" + (" ✅" if not exists else " ❌"))

        # 2.2 create_token
        print(f"Criando token '{TEST_TOKEN}' com quota {TEST_QUOTA}...")
        driver.create_token(TEST_TOKEN, TEST_QUOTA)

        # Verificação direta no Redis
        token_data_hash = driver.redis.hgetall(TOKEN_KEY)
        print(f"Verificação direta (Hash): {token_data_hash}")
        assert token_data_hash is not None
        assert int(token_data_hash.get("quota")) == TEST_QUOTA
        print("✅ Token criado corretamente (modelo HASH).")

        # 2.3 get_token_quota
        print(f"Buscando quota (deve ser {TEST_QUOTA})...")
        quota = driver.get_token_quota(TEST_TOKEN)
        print(f"Quota atual: {quota}" + (" ✅" if quota == TEST_QUOTA else " ❌"))

        # 2.4 decrement_token_quota (loop)
        print("Decrementando quota até zero...")
        for i in range(TEST_QUOTA):
            success = driver.decrement_token_quota(TEST_TOKEN)
            quota = driver.get_token_quota(TEST_TOKEN)
            print(f"Decrementou: {success}, Nova Quota: {quota}" + (" ✅" if success else " ❌"))

        # 2.6 Teste de quota zerada
        print("Tentando decrementar quota zerada (deve falhar)...")
        success = driver.decrement_token_quota(TEST_TOKEN)
        quota = driver.get_token_quota(TEST_TOKEN)
        print(f"Sucesso: {success}, Quota Final: {quota}" + (" ✅" if not success and quota == 0 else " ❌"))

    except Exception as e:
        print(f"❌ ERRO no Teste 2: {e}")

    # Limpa os dados ao final do teste
    cleanup(driver)

    print("\n--- ✅ Playroom finalizado ---")

if __name__ == "__main__":
    main()
