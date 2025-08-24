const axios = require('axios');
const BASE_URL = require('../request-config');
const {describe, beforeEach, afterEach, expect, beforeAll} = require("@jest/globals");
const jwt = require('jsonwebtoken');

axios.defaults.timeout = 10000;

function validateJwtFormat(token) {
    if (typeof token !== 'string') {
        return false;
    }
    try {
        const decoded = jwt.decode(token, { complete: true });

        if (decoded && decoded.header && decoded.payload) {
            return decoded.payload; // Format is valid, return the payload
        }
        return false;
    } catch (err) {
        console.error('JWT format validation failed:', err.message);
        return false;
    }
}

describe('Base Tests - ', () => {

    let testAgent = {
        nome: "GabigOps",
        dataDeIncorporacao: "2023-11-30",
        cargo: "Delegado"
    };

    // These variables will hold the IDs and tokens of the created entities
    let createdAgentId = null;
    let createdCaseId = null;
    let createdUserJWT = "";
    let requestHeaders;

    const properUser = {
        nome: "Gabriel testador",
        email: "gabrieltestador@gmail.com",
        senha: "G4br13lT35t4d0r!!!"
    }

    const properUserLoginPayload = {
        email: properUser.email,
        senha: properUser.senha
    }

    //This block is used to register a user and log him in to get a valid JWT token
    beforeAll(async ()=>{
        try {
            await axios.post(`${BASE_URL}/auth/register`, properUser);
            let userLoginResponse = await axios.post(`${BASE_URL}/auth/login`, properUserLoginPayload);
            createdUserJWT = userLoginResponse.data.access_token;
            requestHeaders = {'Authorization': `Bearer ${createdUserJWT}`};
        } catch (error) {
            console.log(error);
        }
    });

    // CREATES TEST DATA FOR AGENTS AND CASES
    beforeEach(async () => {
        try {
            //Creates agent and fetches id from response
            const agentResponse = await axios.post(`${BASE_URL}/agentes`, testAgent);
            createdAgentId = agentResponse.data.id;

            //Creates testCase using the id from the newly generated agentResponse
            let testCase = {
                titulo: "Roubo do Banco Central",
                descricao: "Alguém hackeou o banco central",
                status: "aberto",
                agente_id: createdAgentId
            };

            //Creates the case and waits for the response
            const caseResponse = await axios.post(`${BASE_URL}/casos`, testCase, {headers: requestHeaders});
            createdCaseId = caseResponse.data.id;

        } catch (error) {
            console.log(error)
        }
    });

    // DELETES TEST DATA FROM AGENTS AND CASES
    afterEach(async () => {
        try {
            // Only attempt to delete entities if they exist
            if (createdCaseId) {
                await axios.delete(`${BASE_URL}/casos/${createdCaseId}`, {headers: requestHeaders});
            }
            if (createdAgentId) {
                await axios.delete(`${BASE_URL}/agentes/${createdAgentId}`, {headers: requestHeaders});
            }
        } catch (error) {
            console.log(error)
        }

        // Reset IDs for the next test
        createdAgentId = null;
        createdCaseId = null;
    });

    describe('Route: /usuarios - ', () => {

        safeTest("USERS: Cria usuário corretamente com status code 201 e os dados inalterados do usuário mais seu ID", async () => {
            try {
                let user = {
                    nome: "Isadora",
                    email: "isa@gmail.com",
                    senha: "SenhaConfiavel1234."
                }
                
                let response = await axios.post(`${BASE_URL}/auth/register`, user);
                expect(response.status).toBe(201);
                expect(response.data).toMatchObject(user);

            } catch (error) {
                console.log(error);
            }
        });

        safeTest("USERS: Loga usuário existente corretamente com status code 200 e retorna JWT válido", async () => {
            try {
                let response = await axios.post(`${BASE_URL}/auth/login`, properUserLoginPayload);
                expect(response.status).toBe(200);
                expect(validateJwtFormat(response.data.access_token)).toBeTruthy();
            } catch (error) {
                console.log(error);
            }
        });

        safeTest("USERS: Faz logout de usuário logado corretamente com status code 200 ou 204 sem retorno e invalida o JWT", async () => {
            try {
                let extraUser = {
                    nome: "Teste",
                    email: "teste@gmail.com",
                    senha: "Senha1234..."
                };

                let loginPayload = {
                    email: extraUser.email,
                    senha: extraUser.senha
                }

                await axios.post(`${BASE_URL}/auth/register`, extraUser);
                let loginResponse = await axios.post(`${BASE_URL}/auth/login`, loginPayload);
                let authHeaders = {'Authorization': `Bearer ${loginResponse.data.access_token}`};

                let response = await axios.post(`${BASE_URL}/auth/logout`, {
                    headers: authHeaders
                });

                let statusValid = response.status === 200 || response.status === 204;
                expect(statusValid).toBeTruthy();
                expect(response.data).toBe('');
            } catch (error) {
                console.log(error)
            }
        });

        safeTest("USERS: Consegue deletar usuário corretamente com status code 204", async () => {
            try {
                let extraUser2 = {
                    nome: "Teste",
                    email: "testeDelete@gmail.com",
                    senha: "Senha1234..."
                };

                let loginPayload2 = {
                    email: extraUser2.email,
                    senha: extraUser2.senha
                }

                await axios.post(`${BASE_URL}/auth/register`, extraUser2);
                let loginResponse = await axios.post(`${BASE_URL}/auth/login`, loginPayload2);
                let authHeaders = {'Authorization': `Bearer ${loginResponse.data.access_token}`};

                let response = await axios.delete(`${BASE_URL}/auth/logout`, {
                    headers: authHeaders
                });

                expect(response.status).toBe(204);
                expect(response.data).toBe('');
            } catch (error) {
                console.log(error)
            }
        });

        safeTest("USERS: JWT retornado no login possui data de expiração válida", async () => {
            try {
                let response = await axios.post(`${BASE_URL}/auth/login`, properUserLoginPayload);
                let jwt = response.data.access_token;
                expect(jwt).toBeDefined();

                const payloadBase64 = jwt.split('.')[1];
                const jsonPayload = Buffer.from(payloadBase64, 'base64').toString();
                const decodedPayload = JSON.parse(jsonPayload);

                const expirationTimestamp = decodedPayload.exp;
                expect(expirationTimestamp).toBeDefined();

                const currentTimeSeconds = Math.floor(Date.now() / 1000);

                expect(expirationTimestamp).toBeGreaterThan(currentTimeSeconds);
            } catch (error) {
                console.log(error)
            }
        });

        //ERROR HANDLING: THESE ARE SOME POSSIBLE ERROR SCENARIOS
        safeTest("USERS: Recebe erro 400 ao tentar criar um usuário com nome vazio", async () => {
            try {
                let user = {
                    nome: "",
                    email: "nomevazio@gmail.com",
                    senha: "SenhaValida1234."
                };
                await axios.post(`${BASE_URL}/auth/register`, user);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("USERS: Recebe erro 400 ao tentar criar um usuário com nome nulo", async () => {
            try {
                let user = {
                    nome: null,
                    email: "nomevazio@gmail.com",
                    senha: "SenhaValida1234."
                };
                await axios.post(`${BASE_URL}/auth/register`, user);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("USERS: Recebe erro 400 ao tentar criar um usuário com email vazio", async () => {
            try {
                let user = {
                    nome: "nomevazio",
                    email: "",
                    senha: "SenhaValida1234."
                };
                await axios.post(`${BASE_URL}/auth/register`, user);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("USERS: Recebe erro 400 ao tentar criar um usuário com email nulo", async () => {
            try {
                let user = {
                    nome: "nomevazio",
                    email: null,
                    senha: "SenhaValida1234."
                };
                await axios.post(`${BASE_URL}/auth/register`, user);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("USERS: Recebe erro 400 ao tentar criar um usuário com senha vazia", async () => {
            try {
                let user = {
                    nome: "nomevazio",
                    email: "nomevazio@gmail.com",
                    senha: ""
                };
                await axios.post(`${BASE_URL}/auth/register`, user);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("USERS: Recebe erro 400 ao tentar criar um usuário com senha curta de mais", async () => {
            try {
                let user = {
                    nome: "nomevazio",
                    email: "nomevazio2@gmail.com",
                    senha: "Senha1."
                };
                await axios.post(`${BASE_URL}/auth/register`, user);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("USERS: Recebe erro 400 ao tentar criar um usuário com senha sem números", async () => {
            try {
                let user = {
                    nome: "nomevazio",
                    email: "nomevazio3@gmail.com",
                    senha: "SenhaDeTeste."
                };
                await axios.post(`${BASE_URL}/auth/register`, user);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("USERS: Recebe erro 400 ao tentar criar um usuário com senha sem caractere especial", async () => {
            try {
                let user = {
                    nome: "nomevazio",
                    email: "nomevazio4@gmail.com",
                    senha: "SenhaDeTeste12345"
                };
                await axios.post(`${BASE_URL}/auth/register`, user);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("USERS: Recebe erro 400 ao tentar criar um usuário com senha sem letra maiúscula", async () => {
            try {
                let user = {
                    nome: "nomevazio",
                    email: "nomevazio5@gmail.com",
                    senha: "senhadeteste12345!!!"
                };
                await axios.post(`${BASE_URL}/auth/register`, user);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("USERS: Recebe erro 400 ao tentar criar um usuário com senha sem letras", async () => {
            try {
                let user = {
                    nome: "nomevazio",
                    email: "nomevazio6@gmail.com",
                    senha: "{}{}12345!!!"
                };
                await axios.post(`${BASE_URL}/auth/register`, user);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("USERS: Recebe erro 400 ao tentar criar um usuário com senha nula", async () => {
            try {
                let user = {
                    nome: "nomevazio",
                    email: "nomevazio7@gmail.com",
                    senha: null
                };
                await axios.post(`${BASE_URL}/auth/register`, user);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("USERS: Recebe erro 400 ao tentar criar um usuário com e-mail já em uso", async () => {
            try {
                let user = {
                    nome: "nomevazio",
                    email: properUser.email,
                    senha: "SenhaBastanteValida123!!!"
                };
                await axios.post(`${BASE_URL}/auth/register`, user);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("USERS: Recebe erro 400 ao tentar criar um usuário com campo extra", async () => {
            try {
                let user = {
                    nome: "nomevazio",
                    email: "nomevazio@gmail.com",
                    senha: "SenhaValida1234.",
                    test: "extra-field"
                };
                await axios.post(`${BASE_URL}/auth/register`, user);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("USERS: Recebe erro 400 ao tentar criar um usuário com campo faltante", async () => {
            try {
                let user = {
                    nome: "nomevazio",
                    senha: "SenhaValida1234.",
                };
                await axios.post(`${BASE_URL}/auth/register`, user);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("USERS: Recebe erro 400 ao tentar fazer logout de usuário com JWT já inválido", async () => {
            try {
                let extraUser = {
                    nome: "Teste2",
                    email: "teste2@gmail.com",
                    senha: "Senha1234..."
                };

                let loginPayload = {
                    email: extraUser.email,
                    senha: extraUser.senha
                }

                await axios.post(`${BASE_URL}/auth/register`, extraUser);
                let loginResponse = await axios.post(`${BASE_URL}/auth/login`, loginPayload);
                let authHeaders = {'Authorization': `Bearer ${loginResponse.data.access_token}`};

                await axios.post(`${BASE_URL}/auth/logout`, {
                    headers: authHeaders
                });

                let response = await axios.post(`${BASE_URL}/auth/logout`, {
                    headers: authHeaders
                });

                expect(response.status).toBe(400);
            } catch (error) {
                console.log(error)
            }
        });
    });

    describe('Route: /agentes - ', () => {

        //Successful scenarios

        safeTest("AGENTS: Cria agentes corretamente com status code 201 e os dados inalterados do agente mais seu ID", async () => {
            let newAgent = {
                nome: "Sophie",
                dataDeIncorporacao: "2024-08-15",
                cargo: "Delegado"
            }

            const response = await axios.post(`${BASE_URL}/agentes`, newAgent, {headers: requestHeaders});
            expect(response.status).toBe(201);
            expect(response.data).toMatchObject(newAgent);
        });

        safeTest('AGENTS: Lista todos os agente corretamente com status code 200 e todos os dados de cada agente listados corretamente', async () => {
            const response = await axios.get(`${BASE_URL}/agentes`, {headers: requestHeaders});
            expect(response.status).toBe(200);
            expect(Array.isArray(response.data)).toBe(true);
            expect(response.data).toEqual(
                expect.arrayContaining([
                    expect.objectContaining({ id: createdAgentId })
                ])
            );
        });

        safeTest('AGENTS: Busca agente por ID corretamente com status code 200 e todos os dados do agente listados dentro de um objeto JSON', async () => {
            const response = await axios.get(`${BASE_URL}/agentes/${createdAgentId}`, {headers: requestHeaders});
            expect(response.status).toBe(200);
            expect(response.data.id).toBe(createdAgentId);
        });

        safeTest('AGENTS: Atualiza dados do agente com por completo (com PUT) corretamente com status code 200 e dados atualizados do agente listados num objeto JSON', async () => {
            const updatedData = {
                nome: "Agent Smith",
                dataDeIncorporacao: "1999-03-31",
                cargo: "Vilão"
            };
            const response = await axios.put(`${BASE_URL}/agentes/${createdAgentId}`, updatedData, {headers: requestHeaders});
            expect(response.status).toBe(200);
            expect(response.data).toMatchObject(updatedData);
        });

        safeTest('AGENTS: Atualiza dados do agente com por completo (com PATCH) corretamente com status code 200 e dados atualizados do agente listados num objeto JSON', async () => {
            const partialUpdate = { cargo: "Agente Especial" };
            const response = await axios.patch(`${BASE_URL}/agentes/${createdAgentId}`, partialUpdate, {headers: requestHeaders});
            expect(response.status).toBe(200);
            expect(response.data.cargo).toBe("Agente Especial");
            expect(response.data.nome).toBe(testAgent.nome);

        });

        safeTest('AGENTS: Deleta dados de agente corretamente com status code 204 e corpo vazio', async () => {
            const response = await axios.delete(`${BASE_URL}/agentes/${createdAgentId}`, {headers: requestHeaders});
            expect(response.status).toBe(204);
            expect(response.data).toBeFalsy();

            //Verify that the user
            try {
                await axios.get(`${BASE_URL}/agentes/${createdAgentId}`, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(true).toBe(true);
            }

            // Nullify the ID to prevent afterEach from trying to delete it again
            createdAgentId = null;
        });

        /**
         * ERROR SCENARIOS
         * These include proper error handling as described in the assignment. It mainly validates proper status codes
         * for different error scenarios.
         */
        safeTest('AGENTS: Recebe status code 400 ao tentar criar agente com payload em formato incorreto', async () => {
            const invalidPayload = {
                dataDeIncorporacao: "2023-11-30",
                cargo: "Delegado"
            };

            try {
                await axios.post(`${BASE_URL}/agentes`, invalidPayload, {headers: requestHeaders});
                //Fail the test if no error is thrown
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest('AGENTS: Recebe status code 401 ao tentar criar agente corretamente mas sem header de autorização com token JWT', async ()=> {
            let newAgent = {
                nome: "Sophie",
                dataDeIncorporacao: "2024-08-15",
                cargo: "Delegado"
            }
            try {
                const response = await axios.post(`${BASE_URL}/agentes`, newAgent);
                expect(response.status).toBe(401);
            } catch (error) {
                expect(error.response.status).toBe(401);
            }
            
        });

        safeTest('AGENTS: Recebe status 404 ao tentar buscar um agente inexistente', async () => {
            const inexistentId = 173128973;

            try {
                await axios.get(`${BASE_URL}/agentes/${inexistentId}`, {headers: requestHeaders});
                //Fail the test if no error is thrown
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest('AGENTS: Recebe status 404 ao tentar buscar um agente com ID em formato inválido', async () => {
            const inexistentId = "Id n aceitavel";

            try {
                await axios.get(`${BASE_URL}/agentes/${inexistentId}`, {headers: requestHeaders});
                //Fail the test if no error is thrown
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest('AGENTS: Recebe status code 401 ao tentar buscar agente corretamente mas sem header de autorização com token JWT', async ()=> {
            try {
                const response = await axios.post(`${BASE_URL}/agentes/${createdAgentId}`);
                expect(response.status).toBe(401);
            } catch (error) {
                expect(error.response.status).toBe(401);
            }
        });

        safeTest('AGENTS: Recebe status code 401 ao tentar buscar todos os agentes corretamente mas sem header de autorização com token JWT', async ()=> {
            try {
                const response = await axios.get(`${BASE_URL}/agentes`);
                expect(response.status).toBe(401);
            } catch (error) {
                expect(error.response.status).toBe(401);
            }
        });

        //Specify more
        safeTest('AGENTS: Recebe status code 400 ao tentar atualizar agente por completo com método PUT e payload em formato incorreto', async () => {
            const invalidPayload = {
                nome: "Agent Smith",
                dataDeIncorporacao: "1999-03-31",
            };

            try {
                await axios.put(`${BASE_URL}/agentes/${createdAgentId}`, invalidPayload, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest('AGENTS: Recebe status code 404 ao tentar atualizar agente por completo com método PUT de agente inexistente', async () => {
            const nonExistentId = 378192;
            const validPayload = {
                nome: "Agente Fantasma",
                dataDeIncorporacao: "2025-01-01",
                cargo: "Assombração"
            };

            try {
                await axios.put(`${BASE_URL}/agentes/${nonExistentId}`, validPayload, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest('AGENTS: Recebe status code 404 ao tentar atualizar agente por completo com método PUT de agente de ID em formato incorreto', async () => {
            const nonExistentId = "Id n aceitavel";
            const validPayload = {
                nome: "Agente Fantasma",
                dataDeIncorporacao: "2025-01-01",
                cargo: "Assombração"
            };

            try {
                await axios.put(`${BASE_URL}/agentes/${nonExistentId}`, validPayload, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest('AGENTS: Recebe status code 401 ao tentar atualizar agente corretamente com PUT mas sem header de autorização com token JWT', async ()=> {
            const updatedData = {
                nome: "Agent Smith",
                dataDeIncorporacao: "1999-03-31",
                cargo: "Vilão"
            };

            try {
                await axios.put(`${BASE_URL}/agentes/${createdAgentId}`, updatedData);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(401);
            }
        });

        //Specify more
        safeTest('AGENTS: Recebe status code 400 ao tentar atualizar agente parcialmente com método PATCH e payload em formato incorreto', async () => {
            const invalidPartialPayload = {
                campoInexistente: "testing"
            };

            try {
                await axios.patch(`${BASE_URL}/agentes/${createdAgentId}`, invalidPartialPayload, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest('AGENTS: Recebe status code 404 ao tentar atualizar agente por parcialmente com método PATCH de agente inexistente', async () => {
            const nonExistentId = 37812731;
            const validPartialPayload = { cargo: "Agente Secreto" };

            try {
                await axios.patch(`${BASE_URL}/agentes/${nonExistentId}`, validPartialPayload, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest('AGENTS: Recebe status code 401 ao tentar atualizar agente corretamente com PATCH mas sem header de autorização com token JWT', async ()=> {
            const updatedData = {
                nome: "Agent Smith",
                dataDeIncorporacao: "1999-03-31",
                cargo: "Vilão"
            };

            try {
                await axios.put(`${BASE_URL}/agentes/${createdAgentId}`, updatedData);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(401);
            }
        });

        safeTest('AGENTS: Recebe status code 404 ao tentar deletar agente inexistente', async () => {
            const nonExistentId = 34267;

            try {
                await axios.delete(`${BASE_URL}/agentes/${nonExistentId}`, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest('AGENTS: Recebe status code 404 ao tentar deletar agente com ID inválido', async () => {
            const nonExistentId = "Not a valid ID";

            try {
                await axios.delete(`${BASE_URL}/agentes/${nonExistentId}`, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest('AGENTS: Recebe status code 401 ao tentar deletar agente corretamente mas sem header de autorização com token JWT', async ()=> {
            try {
                await axios.delete(`${BASE_URL}/agentes/${createdAgentId}`);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(401);
            }
        });
    });

    describe('Route: /casos - ', () => {

        //Successfull scenarios

        safeTest("CASES: Cria casos corretamente com status code 201 e retorna dados inalterados do caso criado mais seu ID", async () => {
            let newCase = {
                titulo: "Titulo",
                descricao: "Description",
                status: "aberto",
                agente_id: createdAgentId
            }

            const response = await axios.post(`${BASE_URL}/casos`, newCase, {headers: requestHeaders});
            expect(response.status).toBe(201);
            expect(response.data.titulo).toBe(newCase.titulo);
            expect(response.data.descricao).toBe(newCase.descricao);
            expect(response.data.status).toBe(newCase.status);
            expect(response.data.agente_id).toBe(newCase.agente_id);
        });

        safeTest('CASES: Lista todos os casos corretamente com status code 200 e retorna lista com todos os dados de todos os casos', async () => {
            const response = await axios.get(`${BASE_URL}/casos`, {headers: requestHeaders});
            expect(response.status).toBe(200);
            expect(Array.isArray(response.data)).toBe(true);
            expect(response.data).toEqual(
                expect.arrayContaining([
                    expect.objectContaining({ id: createdCaseId })
                ])
            );
        });

        safeTest('CASES: Busca caso por ID corretamente com status code 200 e retorna dados do caso', async () => {
            const response = await axios.get(`${BASE_URL}/casos/${createdCaseId}`, {headers: requestHeaders});

            expect(response.status).toBe(200);
            expect(response.data.id).toBe(createdCaseId);
        });

        safeTest('CASES: Atualiza dados de um caso com por completo (com PUT) corretamente com status code 200 e retorna dados atualizados', async () => {
            const updatedData = {
                titulo: "Caso Resolvido",
                descricao: "O ladrão foi pego.",
                status: "solucionado",
                agente_id: createdAgentId
            };
            const response = await axios.put(`${BASE_URL}/casos/${createdCaseId}`, updatedData, {headers: requestHeaders});
            expect(response.status).toBe(200);
            expect(response.data).toMatchObject(updatedData);
        });

        safeTest('CASES: Atualiza dados de um caso parcialmente (com PATCH) corretamente com status code 200 e retorna dados atualizados', async () => {
            const partialUpdate = { status: "solucionado" };
            const response = await axios.patch(`${BASE_URL}/casos/${createdCaseId}`, partialUpdate, {headers: requestHeaders});
            expect(response.status).toBe(200);
            expect(response.data.status).toBe("solucionado");
            expect(response.data.titulo).toBe("Roubo do Banco Central");
        });

        safeTest('CASES: Deleta dados de um caso corretamente com status code 204 e retorna corpo vazio', async () => {
            const temp = createdCaseId;
            const response = await axios.delete(`${BASE_URL}/casos/${createdCaseId}`, {headers: requestHeaders});
            expect(response.status).toBe(204);
            expect(response.data).toBeFalsy();

            try{
                await axios.get(`${BASE_URL}/casos/${temp}`);
                expect(true).toBeFalsy();
            } catch(error){
                expect(true).toBeTruthy();
            }

            // Nullify the ID to prevent afterEach from trying to delete it again
            createdCaseId = null;
        });


        /**
         * ERROR SCENARIOS
         * These include error handling scenarios as described in the assignment
         * It mostly tests the proper status codes in error cases
         */
        //Specify more
        safeTest("CASES: Recebe status code 400 ao tentar criar caso com payload em formato incorreto", async () => {
            const invalidPayload = {
                descricao: "Descrição de um caso inválido",
                status: "aberto",
                agente_id: createdAgentId
            };
            try {
                await axios.post(`${BASE_URL}/casos`, invalidPayload, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("CASES: Recebe status code 404 ao tentar criar caso com ID de agente inexistente", async () => {
            const nonExistentAgentId = 435345;
            const payloadWithInvalidAgent = {
                titulo: "Caso para agente fantasma",
                descricao: "Este agente não existe",
                status: "aberto",
                agente_id: nonExistentAgentId
            };
            try {
                await axios.post(`${BASE_URL}/casos`, payloadWithInvalidAgent, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest("CASES: Recebe status code 404 ao tentar criar caso com ID de agente inválido", async () => {
            const nonExistentAgentId = 435345;
            const payloadWithInvalidAgent = {
                titulo: "Caso para agente fantasma",
                descricao: "Este agente não existe",
                status: "aberto",
                agente_id: nonExistentAgentId
            };
            try {
                await axios.post(`${BASE_URL}/casos`, payloadWithInvalidAgent, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest("CASES: Recebe status code 401 ao tentar criar caso sem header de autorização com JWT", async ()=> {

        });

        safeTest("CASES: Recebe status code 404 ao tentar buscar um caso por ID inválido", async () => {
            const nonExistentCaseId = 3.17;
            try {
                await axios.get(`${BASE_URL}/casos/${nonExistentCaseId}`, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest("CASES: Recebe status code 404 ao tentar buscar um caso por ID inexistente", async () => {
            const nonExistentCaseId = 3420697;
            try {
                await axios.get(`${BASE_URL}/casos/${nonExistentCaseId}`, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest("CASES: Recebe status code 401 ao tentar buscar caso sem header de autorização com JWT", async ()=> {
            try {
                await axios.get(`${BASE_URL}/casos/${createdCaseId}`);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(401);
            }
        });

        safeTest("CASES: Recebe status code 401 ao tentar listar todos os casos sem header de autorização com JWT", async ()=> {
            try {
                await axios.get(`${BASE_URL}/casos`);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(401)
            }
        });

        //Specify more
        safeTest("CASES: Recebe status code 400 ao tentar atualizar um caso por completo com método PUT com payload em formato incorreto", async () => {
            const invalidPayload = {
                titulo: "Título Válido",
                descricao: "Descrição Válida",
                agente_id: createdAgentId
            };
            try {
                await axios.put(`${BASE_URL}/casos/${createdCaseId}`, invalidPayload, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("CASES: Recebe status code 404 ao tentar atualizar um caso por completo com método PUT de um caso inexistente", async () => {
            const nonExistentCaseId = 567765;
            const validPayload = {
                titulo: "Caso Fantasma",
                descricao: "Atualizando um caso que não existe.",
                status: "solucionado",
                agente_id: createdAgentId
            };
            try {
                await axios.put(`${BASE_URL}/casos/${nonExistentCaseId}`, validPayload, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest("CASES: Recebe status code 404 ao tentar atualizar um caso por completo com método PUT de um caso com ID inválido", async () => {
            const nonExistentCaseId = "Invalid ID";
            const validPayload = {
                titulo: "Caso Fantasma",
                descricao: "Atualizando um caso que não existe.",
                status: "solucionado",
                agente_id: createdAgentId
            };
            try {
                await axios.put(`${BASE_URL}/casos/${nonExistentCaseId}`, validPayload, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest("CASES: Recebe status code 401 ao tentar criar caso sem header de autorização com JWT", async ()=> {
            const updatedData = {
                titulo: "Caso Resolvido",
                descricao: "O ladrão foi pego.",
                status: "solucionado",
                agente_id: createdAgentId
            };
            try {
                await axios.put(`${BASE_URL}/casos/${createdCaseId}`, updatedData, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(401);
            }
        });

        safeTest("CASES: Recebe status code 404 ao tentar atualizar um caso parcialmente com método PATCH de um caso inexistente", async () => {
            const nonExistentCaseId = 65757;
            const validPartialPayload = { status: "solucionado" };
            try {
                await axios.patch(`${BASE_URL}/casos/${nonExistentCaseId}`, validPartialPayload, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest("CASES: Recebe status code 404 ao tentar atualizar um caso parcialmente com método PATCH de um caso com ID inválido", async () => {
            const nonExistentCaseId = "Invalid ID";
            const validPartialPayload = { status: "solucionado" };
            try {
                await axios.patch(`${BASE_URL}/casos/${nonExistentCaseId}`, validPartialPayload, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest("CASES: Recebe status code 401 ao tentar atualizar caso parcialmente com método PATCH de um caso sem header de autorização com JWT", async () => {
            try {
                const partialUpdate = { status: "solucionado" };
                response = await axios.patch(`${BASE_URL}/casos/${createdCaseId}`, partialUpdate);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(401);
            }
        });

        safeTest("CASES: Recebe status code 404 ao tentar deletar um caso inexistente", async () => {
            const nonExistentCaseId = 456646;
            try {
                await axios.delete(`${BASE_URL}/casos/${nonExistentCaseId}`, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest("CASES: Recebe status code 404 ao tentar deletar um caso com ID inválido", async () => {
            const nonExistentCaseId = 456646;
            try {
                await axios.delete(`${BASE_URL}/casos/${nonExistentCaseId}`, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest("CASES: Recebe status code 401 ao tentar deletar um caso sem o header de autorização com JWT", async () => {
            try {
                await axios.delete(`${BASE_URL}/casos/${createdCaseId}`);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(401);
            }
        });
    });
});