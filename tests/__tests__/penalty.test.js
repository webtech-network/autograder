const axios = require('axios');
const BASE_URL= require('../request-config');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process')
const {describe, beforeEach, afterEach, beforeAll, test, expect} = require("@jest/globals");

axios.defaults.timeout = 10000;

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

            safeTest("Validation: Consegue alterar ID do agente com método PUT", async ()=> {
                const newId = "das ist kein ID";
                const payload = {
                    id: newId,
                    nome: "Change id",
                    dataDeIncorporacao: "2023-11-30",
                    cargo: "Delegado"
                }

                try{
                    await axios.put(`${BASE_URL}/agentes/${createdAgentId}`, payload);
                    expect(true).toBeTruthy();
                    createdAgentId = null;
                } catch (error) {
                    expect(true).toBeFalsy();
                }

            });

            safeTest("Validation: Consegue alterar ID do agente com método PATCH", async () => {
                const newId = "customId";
                const payload = { id: newId };

                try{
                    await axios.patch(`${BASE_URL}/agentes/${createdAgentId}`, payload);
                    expect(true).toBeTruthy();
                    createdAgentId = null;
                } catch (error) {
                    expect(true).toBeFalsy();
                }
            });

            //Case validation section

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

            safeTest("Validation: Consegue alterar ID do caso com método PUT", async ()=> {
                const newId = "das ist kein ID";
                const payload = {
                    id: newId,
                    titulo: "Change id",
                    descricao: "Caso de teste",
                    status: "aberto",
                    agente_id: createdAgentId
                }

                try{
                    await axios.put(`${BASE_URL}/casos/${createdCaseId}`, payload);
                    expect(true).toBeTruthy();
                    createdCaseId = null;
                } catch (error) {
                    expect(true).toBeFalsy();
                }
            });

            safeTest("Validation: Consegue alterar ID do caso com método PATCH", async () => {
                const newId = "customId";
                const payload = { id: newId };

                try{
                    await axios.patch(`${BASE_URL}/casos/${createdAgentId}`, payload);
                    expect(true).toBeTruthy();
                    createdCaseId = null;
                } catch (error) {
                    expect(true).toBeFalsy();
                }
            });

        })
    });

    /*
    describe('Database tests - ', () => {
        let autograderRoot = '';
        let autograderRootExists = false;

        beforeAll(() => {
            autograderRoot = path.join('/app');
            autograderRootExists = fs.existsSync(autograderRoot);
        });

        safeTest('PERSISTENCE: Dados resistem reinicialização do container', async () => {
            if(!autograderRootExists) return;
            let agentId;
            let persistenceCaseId;

            try {
                let agent = {
                    nome: "Persistence",
                    dataDeIncorporacao: "2000-01-30",
                    cargo: "Fuzileiro"
                }
                let response = await axios.post(`${BASE_URL}/agentes`, agent);
                agentId = await response.data.id;

                let persistenceCase = {
                    titulo: "Persistence",
                    descricao: "Alguém hackeou o banco central",
                    status: "aberto",
                    agente_id: agentId
                }

                let caseResponse = await axios.post(`${BASE_URL}/casos`, persistenceCase);
                persistenceCaseId = await caseResponse.data.id;
            } catch (error){
                console.log(error);
            }

            try {
                execSync("docker compose down", { stdio: 'inherit' });
                execSync("docker compose up -d", { stdio: 'inherit' })
            } catch(error) {
                console.log(error);
            }

            try {
                let agent = await axios.get(`${BASE_URL}/agentes/${agentId}`);
                let responseAgentId = await agent.data.id;
                expect(responseAgentId).toEqual(agentId);
            } catch (error) {
                console.log(error);
            }

            try {
                let caso = await axios.get(`${BASE_URL}/casos/${persistenceCaseId}`);
                let responseCaseId = await caso.data.id;
                expect(responseCaseId).toEqual(responseCaseId);
            } catch (error) {
                console.log(error)
            }
        });
    });*/

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

            expect(dependencyKeys).not.toContain("express");
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


        test('Static files: usuário não seguiu estrutura de arquivos à risca', async () => {
            if(!projectFolderExists) return;

            let gitIgnorePath = path.join(projectRoot, '.gitignore');
            let gitIgnoreExists = fs.existsSync(gitIgnorePath);

            let packageJsonPath = path.join(projectRoot, 'package.json');
            let packageJsonExists = fs.existsSync(packageJsonPath);

            let serverJsonPath = path.join(projectRoot, 'server.js');
            let serverExists = fs.existsSync(serverJsonPath);

            let agentRouterPath = path.join(projectRoot, 'routes/agentesRoutes.js');
            let caseRouterPath = path.join(projectRoot, 'routes/casosRoutes.js');
            let routersExist = fs.existsSync(agentRouterPath) && fs.existsSync(caseRouterPath);

            let agentControllerPath = path.join(projectRoot, 'controllers/agentesController.js');
            let caseControllerPath = path.join(projectRoot, 'controllers/casosController.js');
            let controllersExist = fs.existsSync(agentControllerPath) && fs.existsSync(caseControllerPath);

            let knexFilePath = path.join(projectRoot, 'knexfile.js');
            let knexFileExists = fs.existsSync(knexFilePath);

            let migrationsFolder = path.join(projectRoot, 'db/migrations');
            let migrationsFolderExists = fs.existsSync(migrationsFolder);

            let dbPath = path.join(projectRoot, 'db/db.js');
            let dbExists = fs.existsSync(dbPath);

            let dockerComposeYmlPath = path.join(projectRoot, 'docker-compose.yml');
            let dockerComposeYamlPath = path.join(projectRoot, 'docker-compose.yaml');
            let dockerComposeExists = fs.existsSync(dockerComposeYmlPath) || fs.existsSync(dockerComposeYamlPath);

            let followedStructured = gitIgnoreExists
                && packageJsonExists
                && serverExists
                && routersExist
                && controllersExist
                && knexFileExists
                && migrationsFolderExists
                && dbExists
                && dockerComposeExists;

            expect(followedStructured).toBeFalsy();
        });

        test('ENV: Arquivo .env está presente na root do projeto', () => {
            if(!projectFolderExists) return;

            let envPath = path.join(projectRoot, '.env');
            let envExists = fs.existsSync(envPath);

            expect(envExists).toBeTruthy();
        });
    });
});