const axios = require('axios');
const BASE_URL = require('../request-config')
const {describe, beforeEach, afterEach, expect, beforeAll} = require("@jest/globals");

axios.defaults.timeout = 10000;

describe('Bonus Tests - ', () => {

    // Variables to hold the IDs of all created resources for cleanup
    const createdResourceIds = {
        agents: [],
        cases: []
    };

    // Variables to hold specific resources for individual tests
    let olderAgent, newerAgent, openCase, solvedCase;

    let createdUserJWT = "";
    let requestHeaders;
    const properUser = {
        nome: "Gabriel testador",
        email: "gabrieltestador@gmail.com",
        senha: "G4br13lT35t4d0r!!!"
    }

    beforeAll(async ()=>{
        try {
            const properUserLoginPayload = {
                nome: properUser.nome,
                senha: properUser.senha
            }

            await axios.post(`${BASE_URL}/auth/register`, properUser);
            let userLoginResponse = await axios.post(`${BASE_URL}/auth/login`, properUserLoginPayload);
            createdUserJWT = userLoginResponse.data.access_token;

            requestHeaders = {'Authorization': `Bearer: ${createdUserJWT}`};
        } catch (error) {
            console.log(error);
        }
    });

    beforeEach(async () => {
        // --- Create Agents for Sorting ---
        try{
            olderAgent = (await axios.post(`${BASE_URL}/agentes`, { nome: "Agente Anacrônico", dataDeIncorporacao: "2020-01-15", cargo: "Inspetor" }, {headers: requestHeaders})).data;
            newerAgent = (await axios.post(`${BASE_URL}/agentes`, { nome: "Agente Moderno", dataDeIncorporacao: "2023-06-20", cargo: "Delegado" }, {headers: requestHeaders})).data;
            createdResourceIds.agents.push(olderAgent.id, newerAgent.id);

            // --- Create Cases for Filtering ---
            openCase = (await axios.post(`${BASE_URL}/casos`, { titulo: "Caso em Aberto", descricao: "Investigação em andamento - assalto", status: "aberto", agente_id: olderAgent.id }, {headers: requestHeaders})).data;
            solvedCase = (await axios.post(`${BASE_URL}/casos`, { titulo: "Caso Solucionado", descricao: "Mistério resolvido - estelionato", status: "solucionado", agente_id: newerAgent.id }, {headers: requestHeaders})).data;
            createdResourceIds.cases.push(openCase.id, solvedCase.id);
        } catch (error){
            console.log(error);
        }
    });

    afterEach(async () => {
        // --- Cleanup ---
        try {
            for (const caseId of createdResourceIds.cases) {
                await axios.delete(`${BASE_URL}/casos/${caseId}`, {headers: requestHeaders});
            }
            for (const agentId of createdResourceIds.agents) {
                await axios.delete(`${BASE_URL}/agentes/${agentId}`, {headers: requestHeaders});
            }
        } catch(error){
            console.log(error);
        }
        createdResourceIds.cases = [];
        createdResourceIds.agents = [];
    });

    /**
     * SIMPLE FILTERING TESTS
     * Simple filtering refers to filtering results by simply inserting the value of an attribute to a query string
     */
    describe('Simple Filtering:', () => {
        safeTest('Simple Filtering: Estudante implementou endpoint de filtragem de caso por status corretamente', async() => {
            const response = await axios.get(`${BASE_URL}/casos?status=aberto`, {headers: requestHeaders});

            expect(response.status).toBe(200);
            expect(Array.isArray(response.data)).toBe(true);

            // Ensure every case in the result has the status "aberto"
            response.data.forEach(c => {
                expect(c.status).toBe('aberto');
            });

            // Ensure the open case is present and the solved case is not
            expect(response.data.some(c => c.id === openCase.id)).toBe(true);
            expect(response.data.some(c => c.id === solvedCase.id)).toBe(false);
        });

        safeTest('Simple Filtering: Estudante implementou endpoint de busca de agente responsável por caso', async()=>{
            try{
               let response = await axios.get(`${BASE_URL}/${openCase.id}/agente`, {headers: requestHeaders});
               let agent = await response.data;
               expect(response.status).toBe(200);
               expect(agent.id).toBe(olderAgent.id);
            } catch(error){
                expect(true).toBeFalsy();
                console.log(error);
            }
        });

        safeTest('Simple Filtering: Estudante implementou endpoint de filtragem de caso por agente corretamente', async () => {
            const response = await axios.get(`${BASE_URL}/casos?agente_id=${newerAgent.id}`, {headers: requestHeaders});

            expect(response.status).toBe(200);
            expect(Array.isArray(response.data)).toBe(true);

            response.data.forEach(c => {
                expect(c.agente_id).toBe(newerAgent.id);
            });

            expect(response.data.some(c => c.id === solvedCase.id)).toBe(true);
            expect(response.data.some(c => c.id === openCase.id)).toBe(false);
        });

        safeTest('Simple Filtering: Estudante implementou endpoint de filtragem de casos por keywords no título e/ou descrição', async () => {
            const keyword = "assalto";
            const response = await axios.get(`${BASE_URL}/casos?q=${keyword}`, {headers: requestHeaders});

            expect(response.status).toBe(200);

            expect(Array.isArray(response.data)).toBe(true);

            const allDataHasTheKeyword = response.data.every(caso => {
                const title = caso.titulo || '';
                const description = caso.descricao || '';

                return title.toLowerCase().includes(keyword.toLowerCase()) ||
                    description.toLowerCase().includes(keyword.toLowerCase());
            });

            expect(allDataHasTheKeyword).toBe(true);

            const kw2 = "jaywalking";
            const response2 = await axios.get(`${BASE_URL}/casos?q=${kw2}`, {headers: requestHeaders});

            expect(response.status).toBe(200);
            expect(Array.isArray(response2.data)).toBe(true);
            expect(response.data.length).toBe(0);
        });

        safeTest('Simple filtering: Estudante implementou endpoint de busca de casos do agente', async () => {
            let agentCases = await axios.get(`${BASE_URL}/${newerAgent.id}/casos`, {headers: requestHeaders});
            let agentCasesArray = await agentCases.data;
            expect(Array.isArray(agentCasesArray)).toBeTruthy();

            agentCasesArray.forEach((c) => {
                expect(c.agente_id).toBe(newerAgent.id);
            });
        });
    });

    /**
     * COMPLEX FILTERING TESTS
     * Complex filtering refers to filtering results by inserting the value of an attribute to a query string while also
     * allow other operations, such as sorting, to be performed.
     */
    describe('Complex Filtering:', () => {
        safeTest('Complex Filtering: Estudante implementou endpoint de filtragem de agente por data de incorporacao com sorting em ordem crescente corretamente', async() => {
            let veryOldAgent = {
                nome: "Ednilson",
                dataDeIncorporacao: "1975-03-21",
                cargo: "Coronel"
            }
            let agentCreated = (await axios.post(`${BASE_URL}/agentes`, veryOldAgent, {headers: requestHeaders})).data;
            
            const response = await axios.get(`${BASE_URL}/agentes?sort=dataDeIncorporacao`, {headers: requestHeaders});

            expect(response.status).toBe(200);
            const agents = response.data;

            expect(agents[0]).toMatchObject(agentCreated);
            expect(agents.length).toBeGreaterThan(2);

            for (let i = 0; i < agents.length - 1; i++) {
                const currentAgentDate = agents[i].dataDeIncorporacao;
                const nextAgentDate = agents[i + 1].dataDeIncorporacao; 

                expect(currentAgentDate).toBeLessThanOrEqual(nextAgentDate);
            }
        });

        safeTest('Complex Filtering: Estudante implementou endpoint de filtragem de agente por data de incorporacao com sorting em ordem decrescente corretamente', async() => {
            const veryYoungAgent = {
                nome: "Enzo",
                dataDeIncorporacao: "2025-07-16",
                cargo: "Soldado"
            }

            let agentCreated = (await axios.post(`${BASE_URL}/agentes`, veryYoungAgent, {headers: requestHeaders})).data;

            const response = await axios.get(`${BASE_URL}/agentes?sort=-dataDeIncorporacao`, {headers: requestHeaders});

            expect(response.status).toBe(200);
            const agents = response.data;

            expect(agents[0]).toMatchObject(agentCreated);
            expect(agents.length).toBeGreaterThan(2);
            for (let i = 0; i < agents.length - 1; i++) {
                const currentAgentDate = agents[i].dataDeIncorporacao;
                const nextAgentDate = agents[i + 1].dataDeIncorporacao;
                expect(currentAgentDate).toBeGreaterThanOrEqual(nextAgentDate);
            }

        });
    });

    /**
     * CUSTOM BODY FOR ERRORS
     * User makes a custom body in the following format stating the status code, a message and the invalid fields:
     * {
     *   "status": STATUS_CODE,
     *   "message": "ERROR_MESSAGE"
     *   "errors": [
     *     "INVALID_ARG": "ERROR_MESSAGE"
     *   ]
     * }
     */
    describe('Custom Error:', () => {
        safeTest('Custom Error: Estudante implementou mensagens de erro customizadas para argumentos de agente inválidos corretamente', async () => {
            const invalidPayload = {
                nome: "Agente Inválido",
                dataDeIncorporacao: "30/11/2023", // Wrong format
                cargo: "Recruta"
            };

            try {
                await axios.post(`${BASE_URL}/agentes`, invalidPayload, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
                const errorBody = error.response.data;

                expect(errorBody.status).toBe(400);
                expect(errorBody.message).toBe("Parâmetros inválidos");
                expect(Array.isArray(errorBody.errors)).toBeTruthy();
                expect(errorBody.errors[0]).toHaveProperty('dataDeIncorporacao');
            }
        });

        safeTest('Custom Error: Estudante implementou mensagens de erro customizadas para argumentos de caso inválidos corretamente', async () => {
            const invalidPayload = {
                titulo: "Caso com Status Inválido",
                descricao: "", //Invalid description
                status: "pendente", //Invalid status
                agente_id: null //Invalid agente_id
            };

            try {
                await axios.post(`${BASE_URL}/casos`, invalidPayload, {headers: requestHeaders});
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
                const errorBody = error.response.data;

                expect(errorBody.status).toBe(400);
                expect(errorBody.message).toBe("Parâmetros inválidos");
                expect(Array.isArray(errorBody.errors)).toBeTruthy();
                expect(errorBody.errors[0]).toHaveProperty('descricao');
                expect(errorBody.errors[0]).toHaveProperty('status');
                expect(errorBody.errors[0]).toHaveProperty('agente_id');
            }
        });
    });

    /**
     * Etapa 4 bonus tests
     */

    safeTest("User details: /usuarios/me retorna os dados do usuario logado e status code 200", async ()=> {
        try {
            let response = await axios.get(`${BASE_URL}/usuarios/me`, {headers: requestHeaders});
            let basicUserInfo = {
                nome: properUser.nome,
                email: properUser.email
            }
            expect(response.status).toBe(200);
            expect(response.data).toMatchObject(basicUserInfo);
        } catch (error) {
            expect(true).toBeFalsy();
        }
    });
});