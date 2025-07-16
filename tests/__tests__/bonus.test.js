const axios = require('axios');
const BASE_URL = require('../request-config')
const {describe, beforeEach, afterEach, expect} = require("@jest/globals");


describe('Bonus Tests - ', () => {

    // Variables to hold the IDs of all created resources for cleanup
    const createdResourceIds = {
        agents: [],
        cases: []
    };

    // Variables to hold specific resources for individual tests
    let olderAgent, newerAgent, openCase, solvedCase;

    beforeEach(async () => {
        // --- Create Agents for Sorting ---
        try{
            olderAgent = (await axios.post(`${BASE_URL}/agentes`, { nome: "Agente Anacrônico", dataDeIncorporacao: "2020-01-15", cargo: "Inspetor" })).data;
            newerAgent = (await axios.post(`${BASE_URL}/agentes`, { nome: "Agente Moderno", dataDeIncorporacao: "2023-06-20", cargo: "Delegado" })).data;
            createdResourceIds.agents.push(olderAgent.id, newerAgent.id);

            // --- Create Cases for Filtering ---
            openCase = (await axios.post(`${BASE_URL}/casos`, { titulo: "Caso em Aberto", descricao: "Investigação em andamento - assalto", status: "aberto", agente_id: olderAgent.id })).data;
            solvedCase = (await axios.post(`${BASE_URL}/casos`, { titulo: "Caso Solucionado", descricao: "Mistério resolvido - estelionato", status: "solucionado", agente_id: newerAgent.id })).data;
            createdResourceIds.cases.push(openCase.id, solvedCase.id);
        } catch (error){
            console.log(error);
        }
    });

    afterEach(async () => {
        // --- Cleanup ---
        try {
            for (const caseId of createdResourceIds.cases) {
                await axios.delete(`${BASE_URL}/casos/${caseId}`);
            }
            for (const agentId of createdResourceIds.agents) {
                await axios.delete(`${BASE_URL}/agentes/${agentId}`);
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
        safeTest('Estudante implementou endpoint de filtragem de caso por status corretamente', async() => {
            const response = await axios.get(`${BASE_URL}/casos?status=aberto`);

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

        safeTest('Estudante implementou endpoint de filtragem de caso por agente corretamente', async () => {
            const response = await axios.get(`${BASE_URL}/casos?agente_id=${newerAgent.id}`);

            expect(response.status).toBe(200);
            expect(Array.isArray(response.data)).toBe(true);

            response.data.forEach(c => {
                expect(c.agente_id).toBe(newerAgent.id);
            });

            expect(response.data.some(c => c.id === solvedCase.id)).toBe(true);
            expect(response.data.some(c => c.id === openCase.id)).toBe(false);
        });

        safeTest('Estudante implementou endpoint de filtragem de casos por keywords no título e/ou descrição', async () => {
            const keyword = "assalto";
            const response = await axios.get(`${BASE_URL}/casos?q=${keyword}`);

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
            const response2 = await axios.get(`${BASE_URL}/casos?q=${kw2}`);

            expect(response.status).toBe(200);
            expect(Array.isArray(response2.data)).toBe(true);
            expect(response.data.length).toBe(0);
        });
    });

    /**
     * COMPLEX FILTERING TESTS
     * Complex filtering refers to filtering results by inserting the value of an attribute to a query string while also
     * allow other operations, such as sorting, to be performed.
     */
    describe('Complex Filtering:', () => {
        safeTest('Estudante implementou endpoint de filtragem de agente por data de incorporacao com sorting em ordem crescente corretamente', async() => {
            const response = await axios.get(`${BASE_URL}/agentes?sort=dataDeIncorporacao`);

            expect(response.status).toBe(200);
            const agents = response.data;

            const indexOfOlder = agents.findIndex(a => a.id === olderAgent.id);
            const indexOfNewer = agents.findIndex(a => a.id === newerAgent.id);

            expect(indexOfOlder).toBeLessThan(indexOfNewer);
        });

        safeTest('Estudante implementou endpoint de filtragem de agente por data de incorporacao com sorting em ordem decrescente corretamente', async() => {
            const response = await axios.get(`${BASE_URL}/agentes?sort=-dataDeIncorporacao`);

            expect(response.status).toBe(200);
            const agents = response.data;

            const indexOfOlder = agents.findIndex(a => a.id === olderAgent.id);
            const indexOfNewer = agents.findIndex(a => a.id === newerAgent.id);

            expect(indexOfNewer).toBeLessThan(indexOfOlder);
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
        safeTest('Estudante implementou mensagens de erro customizadas para argumentos de agente inválidos corretamente', async () => {
            const invalidPayload = {
                nome: "Agente Inválido",
                dataDeIncorporacao: "30/11/2023", // Wrong format
                cargo: "Recruta"
            };

            try {
                await axios.post(`${BASE_URL}/agentes`, invalidPayload);
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

        safeTest('Estudante implementou mensagens de erro customizadas para argumentos de caso inválidos corretamente', async () => {
            const invalidPayload = {
                titulo: "Caso com Status Inválido",
                descricao: "", //Invalid description
                status: "pendente", //Invalid status
                agente_id: null //Invalid agente_id
            };

            try {
                await axios.post(`${BASE_URL}/casos`, invalidPayload);
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
});