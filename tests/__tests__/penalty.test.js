const axios = require('axios');
const BASE_URL= require('../request-config');
const fs = require('fs');
const path = require('path');
const {describe, beforeEach, afterEach, beforeAll, test, expect} = require("@jest/globals");

axios.defaults.timeout = 10000;

async function registerAndLoginUser(properUser) {
    try {
        await axios.post(`${BASE_URL}/auth/register`, properUser);

        const properUserLoginPayload = {
            email: properUser.email,
            senha: properUser.senha
        }

        let userLoginResponse = await axios.post(`${BASE_URL}/auth/login`, properUserLoginPayload);

        createdUserJWT = await userLoginResponse.data.access_token;

        if (!createdUserJWT) return { Authorization: `Bearer TESTE` };

        return { Authorization: `Bearer ${createdUserJWT}` };
    } catch (error) {
        console.log(error);
    }
}

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
            requestHeaders = await registerAndLoginUser(properUser);
        });

        // CREATES TEST DATA
        beforeEach(async () => {
            try {
                //Creates agent and fetches id from response
                const agentResponse = await axios.post(`${BASE_URL}/agentes`, testAgent, {headers: requestHeaders});
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
                console.error(error.message);
            }
        });

        // DELETES TEST DATA
        afterEach(async () => {
            // Only attempt to delete entities if they exist
            try {
                if (createdCaseId) {
                    await axios.delete(`${BASE_URL}/casos/${createdCaseId}`, {headers: requestHeaders});
                }
                if (createdAgentId) {
                    await axios.delete(`${BASE_URL}/agentes/${createdAgentId}`, {headers: requestHeaders});
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

            safeTest('Validation: Consegue registrar um agente com dataDeIncorporacao em formato invalido (não é YYYY-MM-DD)', async () => {
                const invalidAgent = { ...testAgent, dataDeIncorporacao: "30-11-2023" };
                try {
                    await axios.post(`${BASE_URL}/agentes`, invalidAgent, {headers: requestHeaders});
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
                    await axios.post(`${BASE_URL}/agentes`, invalidAgent, {headers: requestHeaders});
                    expect(true).toBeTruthy();
                } catch (error) {
                    expect(true).toBeFalsy();
                    console.error(error)
                }
            });

            safeTest("Validation: Consegue registrar agente com nome vazio", async () => {
                let emptyNameAgent = {
                    nome: "",
                    dataDeIncorporacao: "2023-11-30",
                    cargo: "Delegado"
                };
                try {
                    await axios.post(`${BASE_URL}/agentes`, emptyNameAgent, {headers: requestHeaders});
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
                    await axios.post(`${BASE_URL}/agentes`, emptyNameAgent, {headers: requestHeaders});
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
                    await axios.post(`${BASE_URL}/agentes`, emptyNameAgent, {headers: requestHeaders});
                    expect(true).toBeTruthy();
                } catch (error) {
                    expect(true).toBeFalsy();
                    console.error(error);
                }
            });

            safeTest("Validation: Consegue alterar ID do agente com método PUT", async ()=> {
                const newId = 88888888;
                const payload = {
                    id: newId,
                    nome: "Change id",
                    dataDeIncorporacao: "2023-11-30",
                    cargo: "Delegado"
                }

                try{
                    await axios.put(`${BASE_URL}/agentes/${createdAgentId}`, payload, {headers: requestHeaders});
                    expect(true).toBeTruthy();
                    createdAgentId = null;
                } catch (error) {
                    expect(true).toBeFalsy();
                }

            });

            safeTest("Validation: Consegue alterar ID do agente com método PATCH", async () => {
                const newId = 999999;
                const payload = { id: newId };

                try{
                    await axios.patch(`${BASE_URL}/agentes/${createdAgentId}`, payload, {headers: requestHeaders});
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
                    await axios.post(`${BASE_URL}/casos`, invalidCase, {headers: requestHeaders});
                    expect(true).toBeTruthy();
                } catch (error) {
                    expect(true).toBeFalsy();
                    console.error(error)
                }
            });

            safeTest("Validation: Consegue criar um caso com descrição vazia", async () => {
                const invalidCase = { titulo: "Título Válido", descricao: "", status: "aberto", agente_id: createdAgentId };
                try {
                    await axios.post(`${BASE_URL}/casos`, invalidCase, {headers: requestHeaders});
                    expect(true).toBeTruthy();
                } catch (error) {
                    expect(true).toBeFalsy();
                    console.error(error)
                }
            });

            safeTest('Validation: Consegue registrar caso com agente inexistente', async () => {
                const nonExistentAgentId = 999999;
                const invalidCase = { titulo: "Título Válido", descricao: "Descrição válida", status: "aberto", agente_id: nonExistentAgentId };
                try {
                    await axios.post(`${BASE_URL}/casos`, invalidCase, {headers: requestHeaders});
                    expect(true).toBeTruthy();
                } catch (error) {
                    expect(true).toBeFalsy();
                    console.error(error);
                }
            });

            safeTest("Validation: Consegue atualizar um caso com status que não seja 'aberto' ou 'solucionado'", async () => {
                const invalidCase = { titulo: "Título Válido", descricao: "Desc", status: "inválido", agente_id: createdAgentId };
                try {
                    await axios.post(`${BASE_URL}/casos`, invalidCase, {headers: requestHeaders});
                    expect(true).toBeTruthy();
                } catch (error) {
                    expect(true).toBeFalsy();
                    console.error(error)
                }
            });

            safeTest("Validation: Consegue alterar ID do caso com método PUT", async ()=> {
                const newId = 1234567;
                const payload = {
                    id: newId,
                    titulo: "Change id",
                    descricao: "Caso de teste",
                    status: "aberto",
                    agente_id: createdAgentId
                }

                try{
                    await axios.put(`${BASE_URL}/casos/${createdCaseId}`, payload, {headers: requestHeaders});
                    expect(true).toBeTruthy();
                    createdCaseId = null;
                } catch (error) {
                    expect(true).toBeFalsy();
                }
            });

            safeTest("Validation: Consegue alterar ID do caso com método PATCH", async () => {
                const newId = 420420;
                const payload = { id: newId };

                try{
                    await axios.patch(`${BASE_URL}/casos/${createdAgentId}`, payload, {headers: requestHeaders});
                    expect(true).toBeTruthy();
                    createdCaseId = null;
                } catch (error) {
                    expect(true).toBeFalsy();
                }
            });
        });

        describe("Cybersecurity related tests: - ", () => {
            safeTest("SECURITY: Aplicação apresenta vulnerabilidade alg none", async ()=>{
                const tokenParts = createdUserJWT.split('.');
                
                const header = JSON.parse(Buffer.from(tokenParts[0], 'base64url').toString('utf8'));
                const payload = JSON.parse(Buffer.from(tokenParts[1], 'base64url').toString('utf8'));

                header.alg = 'none';
                payload.isAdmin = true;

                const maliciousHeader = Buffer.from(JSON.stringify(header)).toString('base64url');
                const maliciousPayload = Buffer.from(JSON.stringify(payload)).toString('base64url');

                const maliciousToken = `${maliciousHeader}.${maliciousPayload}.`;
                const maliciousRequestHeader = {'Authorization': `Bearer ${maliciousToken}`};
                
                try {
                    await axios.get(`${BASE_URL}/agentes`, maliciousRequestHeader);
                    expect(true).toBeTruthy();
                } catch (error) {
                    expect(error.response.status).toBe(401);
                }
                
            });
        });
    });

    //TESTS RELATED TO THE USER'S FILE ORGANIZATION AND CONFIG FILES
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
            let authRouterPath = path.join(projectRoot, 'routes/authRoutes.js');
            let routersExist = fs.existsSync(agentRouterPath) && fs.existsSync(caseRouterPath) && fs.existsSync(authRouterPath);

            let agentControllerPath = path.join(projectRoot, 'controllers/agentesController.js');
            let caseControllerPath = path.join(projectRoot, 'controllers/casosController.js');
            let authControllerPath = path.join(projectRoot, 'controllers/authController.js');
            let controllersExist = fs.existsSync(agentControllerPath) && fs.existsSync(caseControllerPath) && fs.existsSync(authControllerPath);

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