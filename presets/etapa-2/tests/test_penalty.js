const axios = require('axios');
const BASE_URL= require('../request-config');
const fs = require('fs');
const path = require('path');
const {describe, beforeEach, afterEach, beforeAll, test, expect} = require("@jest/globals");
const setup = require("../setup"); // Assuming safeTest is defined in a separate file
const safeTest = setup.safeTest; // Importing safeTest from setup

describe('Penalty Tests - ', () => {

    /**
     *     BLOCK TO RUN ALL PENALTY TESTS THAT REQUIRE MAKING REQUESTS
     *     It creates and deletes test data for each test
     */
    describe('Requests Tests - ', () => {

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
                console.error(error.message);
                //throw new Error(`There was an error during the beforeEach setup in the penalty tests: ${error.message}`);
            }
        });

        // DELETES TEST DATA
        afterEach(async () => {
            // Only attempt to delete entities if they exist
            try {
                if (createdCaseId) {
                    await axios.delete(`${BASE_URL}/casos/${createdCaseId}`);
                }
                if (createdAgentId) {
                    await axios.delete(`${BASE_URL}/agentes/${createdAgentId}`);
                }
            } catch (error) {
                console.error(error);
            }

            // Reset IDs for the next test
            createdAgentId = null;
            createdCaseId = null;
        });

        describe('Logic and validation errors', () => {

            //Agent validation section

            safeTest('Validation: ID utilizado para agentes não é UUID', () => {
                const regex = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;
                expect(regex.test(createdAgentId)).toBeFalsy();
            });

            safeTest('Validation: Consegue registrar um agente com dataDeIncorporacao em formato invalido (não é YYYY-MM,DD)', async () => {
                const invalidAgent = { ...testAgent, dataDeIncorporacao: "30-11-2023" };
                try {
                    await axios.post(`${BASE_URL}/agentes`, invalidAgent);
                    expect(true).toBeTruthy();
                } catch (error) {
                    expect(true).toBeFalsy();
                    console.error(error);
                }
            });

            safeTest('Validation: Consegue registrar agente com data de incorporação no futuro', async () => {
                const futureYear = new Date().getFullYear() + 1;
                const invalidAgent = { ...testAgent, dataDeIncorporacao: `${futureYear}-01-01` };
                try {
                    await axios.post(`${BASE_URL}/agentes`, invalidAgent);
                    expect(true).toBeTruthy();
                } catch (error) {
                    expect(true).toBeFalsy();
                    console.error(error)
                    //expect(error.response.status).toBe(400);
                }
            });

            safeTest("Validation: Consegue registrar agente com nome vazio", async () => {
                let emptyNameAgent = {
                    nome: "",
                    dataDeIncorporacao: "2023-11-30",
                    cargo: "Delegado"
                };
                try {
                    await axios.post(`${BASE_URL}/agentes`, emptyNameAgent);
                    expect(true).toBeTruthy();
                } catch (error) {
                    expect(true).toBeFalsy();
                    console.error(error);
                }
            });

            safeTest("Validation: Consegue registrar agente com data vazia", async () => {
                let emptyNameAgent = {
                    nome: "Testing",
                    dataDeIncorporacao: "",
                    cargo: "Delegado"
                };
                try {
                    await axios.post(`${BASE_URL}/agentes`, emptyNameAgent);
                    expect(true).toBeTruthy();
                } catch (error) {
                    expect(true).toBeFalsy();
                    console.error(error);
                }
            });

            safeTest("Validation: Consegue registrar agente com cargo vazio", async () => {
                let emptyNameAgent = {
                    nome: "Testing",
                    dataDeIncorporacao: "2023-11-30",
                    cargo: ""
                };
                try {
                    await axios.post(`${BASE_URL}/agentes`, emptyNameAgent);
                    expect(true).toBeTruthy();
                } catch (error) {
                    expect(true).toBeFalsy();
                    console.error(error);
                }
            });


            //Case validation section

            safeTest('Validation: ID utilizado para casos não é UUID', () => {
                const regex = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;
                expect(regex.test(createdCaseId)).toBeFalsy();
            });

            safeTest("Validation: Consegue criar um caso com título vazio", async() => {
                const invalidCase = { titulo: "", descricao: "Descrição válida", status: "aberto", agente_id: createdAgentId };
                try {
                    await axios.post(`${BASE_URL}/casos`, invalidCase);
                    expect(true).toBeTruthy();
                } catch (error) {
                    expect(true).toBeFalsy();
                    console.error(error)
                    //expect(error.response.status).toBe(400);
                }
            });

            safeTest("Validation: Consegue criar um caso com descrição vazia", async () => {
                const invalidCase = { titulo: "Título Válido", descricao: "", status: "aberto", agente_id: createdAgentId };
                try {
                    await axios.post(`${BASE_URL}/casos`, invalidCase);
                    expect(true).toBeTruthy();
                } catch (error) {
                    expect(true).toBeFalsy();
                    console.error(error)
                    //expect(error.response.status).toBe(400);
                }
            });

            safeTest('Validation: Consegue registrar caso com agente inexistente', async () => {
                const nonExistentAgentId = "Isso com ctz n é um ID";
                const invalidCase = { titulo: "Título Válido", descricao: "Descrição válida", status: "aberto", agente_id: nonExistentAgentId };
                try {
                    await axios.post(`${BASE_URL}/casos`, invalidCase);
                    expect(true).toBeTruthy();
                } catch (error) {
                    expect(true).toBeFalsy();
                    //expect(error.response.status).toBe(404);
                    console.error(error);
                }
            });

            safeTest("Validation: Consegue atualizar um caso com status que não seja 'aberto' ou 'solucionado'", async () => {
                const invalidCase = { titulo: "Título Válido", descricao: "Desc", status: "inválido", agente_id: createdAgentId };
                try {
                    await axios.post(`${BASE_URL}/casos`, invalidCase);
                    expect(true).toBeTruthy();
                } catch (error) {
                    expect(true).toBeFalsy();
                    console.error(error)
                }
            });

        })
    });


    //TESTS RELATED TO THE USER'S FILE ORGANIZATION AND CONFIG FILES (ALREADY MADE)
    describe('Static File Organization - ', () => {
        let projectRoot = '';
        let projectFolderExists = false;

        beforeAll(() => {
            projectRoot = path.join(process.env.GITHUB_WORKSPACE || '', "submission");

            if (fs.existsSync(projectRoot)) {
                projectFolderExists = true;
            }
            console.log(`Project root is: ${projectRoot}`);
            console.log(`Project folder exists: ${projectFolderExists}`);
        });

        //ADAPT TO NEW DEPENDENCIES
        test('Static files: projeto não contém dependências obrigatórias', () => {
            if (!projectFolderExists) return;

            let packageJsonPath = path.join(projectRoot, 'package.json');
            let fileExists = fs.existsSync(packageJsonPath);

            if (!fileExists) {
                console.log(`package.json file does not exist - path used: ${packageJsonPath}`);
                return;
            }

            const fileContent = fs.readFileSync(packageJsonPath, 'utf8');
            const packageJson = JSON.parse(fileContent);
            const dependencies = packageJson.dependencies || {};
            const dependencyKeys = Object.keys(dependencies);

            expect(dependencyKeys.length).toBeLessThan(3);
            expect(dependencyKeys).not.toContain("express");
            expect(dependencyKeys).not.toContain("swagger-jsdoc");
            expect(dependencyKeys).not.toContain("swagger-ui-express");
        });

        test('Static files: .gitignore não contém pasta node_modules', () => {
            if (!projectFolderExists) return;

            let gitIgnorePath = path.join(projectRoot, '.gitignore');
            let fileExists = fs.existsSync(gitIgnorePath);

            if (!fileExists) return;

            let isCorrectlyIgnored = false;

            if (fs.existsSync(gitIgnorePath)) {
                const gitignoreContent = fs.readFileSync(gitIgnorePath, 'utf8');

                if (gitignoreContent.includes('node_modules')) {
                    isCorrectlyIgnored = true;
                }
            }
            expect(isCorrectlyIgnored).toBe(false);
        });

        test('Static files: usuário não possui arquivo para documentação swagger', async () => {
            if(!projectFolderExists) return;

            let swaggerFilePathJson = path.join(projectRoot, 'docs/swagger.json');
            let swaggerFilePathYaml = path.join(projectRoot, 'docs/swagger.yaml');
            let fileExists = fs.existsSync(swaggerFilePathJson) || fs.existsSync(swaggerFilePathYaml);

            expect(fileExists).toBeFalsy();
        });

        test('Static files: usuário não seguiu estrutura de arquivos à risca', async () => {
            if(!projectFolderExists) return;

            let swaggerFilePathJson = path.join(projectRoot, 'docs/swagger.json');
            let swaggerFilePathYaml = path.join(projectRoot, 'docs/swagger.yaml');
            let swaggerFileExists = fs.existsSync(swaggerFilePathJson) || fs.existsSync(swaggerFilePathYaml);

            let gitIgnorePath = path.join(projectRoot, '.gitignore');
            let gitIgnoreExists = fs.existsSync(gitIgnorePath);

            let packageJsonPath = path.join(projectRoot, 'package.json');
            let packageJsonExists = fs.existsSync(packageJsonPath);

            let serverJsonPath = path.join(projectRoot, 'server.json');
            let serverExists = fs.existsSync(serverJsonPath);

            let agentRouterPath = path.join(projectRoot, 'routes/agentesRoutes.js');
            let caseRouterPath = path.join(projectRoot, 'routes/casosRoutes.js');
            let routersExist = fs.existsSync(agentRouterPath) && fs.existsSync(caseRouterPath);

            let agentControllerPath = path.join(projectRoot, 'controllers/agentesController.js');
            let caseControllerPath = path.join(projectRoot, 'controllers/casosController.js');
            let controllersExist = fs.existsSync(agentControllerPath) && fs.existsSync(caseControllerPath);

            let agentRepositoryPath = path.join(projectRoot, 'repositories/agentesRepository.js');
            let caseRepositoryPath = path.join(projectRoot, 'repositories/casosRepository.js');
            let repositoriesExist = fs.existsSync(caseRepositoryPath) && fs.existsSync(agentRepositoryPath);

            let followedStructured = swaggerFileExists
                && gitIgnoreExists
                && packageJsonExists
                && serverExists
                && routersExist
                && controllersExist
                && repositoriesExist;

            expect(followedStructured).toBeFalsy();
        });
    });
});