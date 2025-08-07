const axios = require('axios');
const BASE_URL = require('../request-config');
const {describe, beforeEach, afterEach, expect} = require("@jest/globals");

describe('Base Tests - ', () => {

    let testAgent = {
        nome: "GabigOps",
        dataDeIncorporacao: "2023-11-30",
        cargo: "Delegado"
    };

    // These variables will hold the IDs of the created entities
    let createdAgentId = null;
    let createdCaseId = null;

    // CREATES TEST DATA
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
            const caseResponse = await axios.post(`${BASE_URL}/casos`, testCase);
            createdCaseId = caseResponse.data.id;

        } catch (error) {
            console.log(error)
        }
    });

    // DELETES TEST DATA
    afterEach(async () => {
        try {
            // Only attempt to delete entities if they exist
            if (createdCaseId) {
                await axios.delete(`${BASE_URL}/casos/${createdCaseId}`);
            }
            if (createdAgentId) {
                await axios.delete(`${BASE_URL}/agentes/${createdAgentId}`);
            }
        } catch (error) {
            console.log(error)
        }

        // Reset IDs for the next test
        createdAgentId = null;
        createdCaseId = null;
    });

    describe('Route: /agentes - ', () => {

        //Successful scenarios

        safeTest("CREATE: Cria agentes corretamente", async () => {
            let newAgent = {
                nome: "Sophie",
                dataDeIncorporacao: "2024-08-15",
                cargo: "Delegado"
            }

            const response = await axios.post(`${BASE_URL}/agentes`, newAgent);
            expect(response.status).toBe(201);
            expect(response.data).toMatchObject(newAgent);
        });

        safeTest('READ: Lista todos os agente corretamente', async () => {
            const response = await axios.get(`${BASE_URL}/agentes`);
            expect(response.status).toBe(200);
            expect(Array.isArray(response.data)).toBe(true);
            expect(response.data).toEqual(
                expect.arrayContaining([
                    expect.objectContaining({ id: createdAgentId })
                ])
            );
        });

        safeTest('READ: Busca agente por ID corretamente', async () => {
            const response = await axios.get(`${BASE_URL}/agentes/${createdAgentId}`);
            expect(response.status).toBe(200);
            expect(response.data.id).toBe(createdAgentId);
        });

        safeTest('UPDATE: Atualiza dados do agente com por completo (com PUT) corretamente', async () => {
            const updatedData = {
                nome: "Agent Smith",
                dataDeIncorporacao: "1999-03-31",
                cargo: "Vilão"
            };
            const response = await axios.put(`${BASE_URL}/agentes/${createdAgentId}`, updatedData);
            expect(response.status).toBe(200);
            expect(response.data).toMatchObject(updatedData);
        });

        safeTest('UPDATE: Atualiza dados do agente com por completo (com PATCH) corretamente', async () => {
            const partialUpdate = { cargo: "Agente Especial" };
            const response = await axios.patch(`${BASE_URL}/agentes/${createdAgentId}`, partialUpdate);
            expect(response.status).toBe(200);
            expect(response.data.cargo).toBe("Agente Especial");
            expect(response.data.nome).toBe(testAgent.nome);

        });

        safeTest('DELETE: Deleta dados de agente corretamente', async () => {
            const response = await axios.delete(`${BASE_URL}/agentes/${createdAgentId}`);
            expect(response.status).toBe(204);
            expect(response.data).toBeFalsy();

            //Verify that the user
            let checkResponse;
            try {
                checkResponse = await axios.get(`${BASE_URL}/agentes/${createdAgentId}`);
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
        safeTest('CREATE: Recebe status code 400 ao tentar criar agente com payload em formato incorreto', async () => {
            const invalidPayload = {
                dataDeIncorporacao: "2023-11-30",
                cargo: "Delegado"
            };

            try {
                await axios.post(`${BASE_URL}/agentes`, invalidPayload);
                //Fail the test if no error is thrown
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest('READ: Recebe status 404 ao tentar buscar um agente inexistente', async () => {
            const inexistentId = "dwjnclkwmkemwdl";

            try {
                await axios.get(`${BASE_URL}/agentes/${inexistentId}`,);
                //Fail the test if no error is thrown
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest('UPDATE: Recebe status code 400 ao tentar atualizar agente por completo com método PUT e payload em formato incorreto', async () => {
            const invalidPayload = {
                nome: "Agent Smith",
                dataDeIncorporacao: "1999-03-31",
            };

            try {
                await axios.put(`${BASE_URL}/agentes/${createdAgentId}`, invalidPayload);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest('UPDATE: Recebe status code 404 ao tentar atualizar agente por completo com método PUT de agente inexistente', async () => {
            const nonExistentId = crypto.randomUUID().toString();
            const validPayload = {
                nome: "Agente Fantasma",
                dataDeIncorporacao: "2025-01-01",
                cargo: "Assombração"
            };

            try {
                await axios.put(`${BASE_URL}/agentes/${nonExistentId}`, validPayload);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest('UPDATE: Recebe status code 400 ao tentar atualizar objeto parcialmente com método PATCH e payload em formato incorreto', async () => {
            const invalidPartialPayload = {
                dataDeIncorporacao: "01-01-2025"
            };

            try {
                await axios.patch(`${BASE_URL}/agentes/${createdAgentId}`, invalidPartialPayload);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest('UPDATE: Recebe status code 404 ao tentar atualizar agente por parcialmente com método PATCH de agente inexistente', async () => {
            const nonExistentId = crypto.randomUUID().toString();
            const validPartialPayload = { cargo: "Agente Secreto" };

            try {
                await axios.patch(`${BASE_URL}/agentes/${nonExistentId}`, validPartialPayload);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest('DELETE: Recebe status code 404 ao tentar deletar agente inexistente', async () => {
            const nonExistentId = crypto.randomUUID().toString();

            try {
                await axios.delete(`${BASE_URL}/agentes/${nonExistentId}`);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });
    });

    describe('Route: /casos - ', () => {

        //Successfull scenarios

        safeTest("CREATE: Cria casos corretamente", async () => {
            let newCase = {
                titulo: "Titulo",
                descricao: "Description",
                status: "aberto",
                agente_id: createdAgentId
            }

            const response = await axios.post(`${BASE_URL}/casos`, newCase);
            expect(response.status).toBe(201);
            expect(response.data.titulo).toBe(newCase.titulo);
            expect(response.data.descricao).toBe(newCase.descricao);
            expect(response.data.status).toBe(newCase.status);
            expect(response.data.agente_id).toBe(newCase.agente_id);
        });

        safeTest('Lista todos os casos corretamente', async () => {
            const response = await axios.get(`${BASE_URL}/casos`);
            expect(response.status).toBe(200);
            expect(Array.isArray(response.data)).toBe(true);
            expect(response.data).toEqual(
                expect.arrayContaining([
                    expect.objectContaining({ id: createdCaseId })
                ])
            );
        });

        safeTest('READ: Busca caso por ID corretamente', async () => {
            const response = await axios.get(`${BASE_URL}/casos/${createdCaseId}`);

            expect(response.status).toBe(200);
            expect(response.data.id).toBe(createdCaseId);
        });

        safeTest('UPDATE: Atualiza dados de um caso com por completo (com PUT) corretamente', async () => {
            const updatedData = {
                titulo: "Caso Resolvido",
                descricao: "O ladrão foi pego.",
                status: "solucionado",
                agente_id: createdAgentId
            };
            const response = await axios.put(`${BASE_URL}/casos/${createdCaseId}`, updatedData);
            expect(response.status).toBe(200);
            expect(response.data).toMatchObject(updatedData);
        });

        safeTest('UPDATE: Atualiza dados de um caso parcialmente (com PATCH) corretamente', async () => {
            const partialUpdate = { status: "solucionado" };
            const response = await axios.patch(`${BASE_URL}/casos/${createdCaseId}`, partialUpdate);
            expect(response.status).toBe(200);
            expect(response.data.status).toBe("solucionado");
            expect(response.data.titulo).toBe("Roubo do Banco Central");
        });

        safeTest('DELETE: Deleta dados de um caso corretamente', async () => {
            const temp = createdCaseId;
            const response = await axios.delete(`${BASE_URL}/casos/${createdCaseId}`);
            expect(response.status).toBe(204);
            expect(response.data).toBeFalsy();

            let check;
            try{
                check = await axios.get(`${BASE_URL}/casos/${temp}`);
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
        safeTest("CREATE: Recebe status code 400 ao tentar criar caso com payload em formato incorreto", async () => {
            const invalidPayload = {
                descricao: "Descrição de um caso inválido",
                status: "aberto",
                agente_id: createdAgentId
            };
            try {
                await axios.post(`${BASE_URL}/casos`, invalidPayload);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("CREATE: Recebe status code 404 ao tentar criar caso com id de agente inválido/inexistente", async () => {
            const nonExistentAgentId = "hiwnqjdnkqndoqdjiqwdn";
            const payloadWithInvalidAgent = {
                titulo: "Caso para agente fantasma",
                descricao: "Este agente não existe",
                status: "aberto",
                agente_id: nonExistentAgentId
            };
            try {
                await axios.post(`${BASE_URL}/casos`, payloadWithInvalidAgent);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest("READ: Recebe status code 404 ao tentar buscar um caso por ID inválido", async () => {
            const nonExistentCaseId = "hbkdqjnwefu";
            try {
                await axios.get(`${BASE_URL}/casos/${nonExistentCaseId}`);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest("UPDATE: Recebe status code 400 ao tentar atualizar um caso por completo com método PUT com payload em formato incorreto", async () => {
            const invalidPayload = {
                titulo: "Título Válido",
                descricao: "Descrição Válida",
                agente_id: createdAgentId
            };
            try {
                await axios.put(`${BASE_URL}/casos/${createdCaseId}`, invalidPayload);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(400);
            }
        });

        safeTest("UPDATE: Recebe status code 404 ao tentar atualizar um caso por completo com método PUT de um caso inexistente", async () => {
            const nonExistentCaseId = "crcashknnwe";
            const validPayload = {
                titulo: "Caso Fantasma",
                descricao: "Atualizando um caso que não existe.",
                status: "solucionado",
                agente_id: createdAgentId
            };
            try {
                await axios.put(`${BASE_URL}/casos/${nonExistentCaseId}`, validPayload);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });


        safeTest("UPDATE: Recebe status code 404 ao tentar atualizar um caso parcialmente com método PATCH de um caso inexistente", async () => {
            const nonExistentCaseId = "caso-inexistente";
            const validPartialPayload = { status: "solucionado" };
            try {
                await axios.patch(`${BASE_URL}/casos/${nonExistentCaseId}`, validPartialPayload);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });

        safeTest("DELETE: Recebe status code 404 ao tentar deletar um caso inexistente", async () => {
            const nonExistentCaseId = crypto.randomUUID().toString();
            try {
                await axios.delete(`${BASE_URL}/casos/${nonExistentCaseId}`);
                expect(true).toBeFalsy();
            } catch (error) {
                expect(error.response.status).toBe(404);
            }
        });
    });
});