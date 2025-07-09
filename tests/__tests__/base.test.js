const axios = require('axios');
const cheerio = require('cheerio');
const { BASE_URL } = require('../config');

let axiosNoRedirect = axios.create({ maxRedirects: 0 });

describe('Base Tests - ', () => {
  describe('Route: / - ', () => {
    let response;

    beforeAll(async () => {
      try {
        response = await axios.get(BASE_URL)
      } catch (error) {
        if (error.code === 'ECONNREFUSED') throw new Error(`Connection refused at ${BASE_URL}. Is the Express server running?`);
        throw new Error(`An unexpected error occurred while testing GET /: ${error.message}`);
      }
    });

    // 1) --- Basic connectivity checks ---
    describe('Status code and headers', () => {

      test('deve retornar status code 200', () => {
        expect(response.status).toBe(200);
      });

      test('deve retornar header Content-Type text/html', () => {
        expect(response.headers['content-type']).toMatch(/html/);
      });
    });


    // 2) --- HTML content checks ---
    describe('HTML Content Analysis', () => {
      let $;
      let $form;

      beforeAll(() => {
        $ = cheerio.load(response.data);
        $form = $('form')
      });

      test('deve conter pelo menos um formulário', () => {
        expect($form.length).toBeGreaterThan(0);
      });

      test('form deve conter botão do tipo submit', () => {
        const submitButton = $('button[type="submit"], input[type="submit"]');
        expect(submitButton.length).toBeGreaterThan(0);
      });

      const expectedFormFields = [
        {
          name: 'nome',
          acceptableSelectors: ['input[type="text"]', 'textarea']
        },
        {
          name: 'ingredientes',
          acceptableSelectors: ['input[type="text"]', 'textarea']
        }
      ];

      test('deve conter dois campos de input do tipo texto com atributos "name" sendo "nome" no primeiro e "ingredentes" no segundo', () => {
        expectedFormFields.forEach(field => {
          let foundField = false;

          for (const selector of field.acceptableSelectors) {
            const $input = $form.find(`${selector}[name="${field.name}"]`);
            if ($input.length > 0) foundField = true;
          }
          expect(foundField).toBe(true);
        });
      });
    });
  }
  );


  /**
   * Tests for the suggestion route
   */
  describe('Route: /sugestao - ', () => {
    const suggestion = {
      nome: "Banh mi",
      ingredientes: "cenoura, o nabo, a cebola, o açúcar e vinagre de arroz"
    };

    let response;
    let $;
    let queryString;

    beforeAll(async () => {
      queryString = new URLSearchParams(suggestion).toString();
      try {
        response = await axios.get(`${BASE_URL}/sugestao?${queryString}`);
        $ = cheerio.load(response.data);
      } catch (error) {
        if (error.code === 'ECONNREFUSED') {
          throw new Error(`Connection refused at ${BASE_URL}/sugestao?${queryString}. Is the Express server running?`);
        }
        if(error.response) response = error.response;
        else {
          throw new Error(`An unexpected error occurred while testing GET /sugestao: ${error.message}`);
        }
        $ = cheerio.load(response.data);
      }
    });

    test('deve aceitar uma requisição GET com query string contendo parâmetros "nome" e "ingredientes"', () => {
      expect(response.config.url).toContain(`?${queryString}`);
      expect(response.config.method).toBe('get');
    });

    test('deve retornar status code 200 com content-type html', () => {
      expect(response.status).toBe(200);
      expect(response.headers['content-type']).toMatch(/html/);
    });

    test('não deve retornar um redirect (status não deve ser 3xx)', () => {
      const isRedirect = response.status >= 300 && response.status < 400;
      expect(isRedirect).toBe(false);
    });


    describe('HTML Content Analysis', () => {
      test('deve exibir o nome enviado via query string na página HTML', () => {
        expect($.html()).toContain(suggestion.nome);
      });

      test('deve exibir os ingredientes enviados via query string na página HTML', () => {
        expect($.html()).toContain(suggestion.ingredientes);
      });

      test('deve conter umad âncora para a rota raíz /', () => {
        const rootLink = $('a[href="/"]');
        expect(rootLink.length).toBeGreaterThanOrEqual(1);
      });
    });
  });


  describe('Route: /contato (GET) - ', () => {
    let response;
    let $;
    beforeAll(async () => {
      try {
        response = await axios.get(`${BASE_URL}/contato`);
        $ = cheerio.load(response.data);
      } catch (error) {
        if (error.code === 'ECONNREFUSED') {
          throw new Error(`Connection refused at ${BASE_URL}/contato. Is the Express server running?`);
        }
        
        if(response.error) response = error.response;
        else {
          throw new Error(`An unexpected error occurred while testing GET /contato: ${error.message}`);
        }
        $ = cheerio.load(response.data);
      }
    });

    test('deve retornar status code 200 e Content-type text/html', () => {
      expect(response.status).toBe(200);
      expect(response.headers['content-type']).toMatch(/html/);
    });

    test('deve conter um campo de input ou textarea do tipo texto com atributo name como "nome"', () => {
      const nomeInput = $('[name="nome"]');
      expect(nomeInput.length).toBeGreaterThan(0);
      expect(nomeInput.is('input[type="text"]') || nomeInput.is('textarea')).toBe(true);
    });

    test('deve conter um campo de input do tipo email ou texto com atributo name como "email"', () => {
      const emailInput = $('[name="email"]');
      expect(emailInput.length).toBeGreaterThan(0);
      expect(emailInput.is('input[type="email"]') || emailInput.is('input[type="text"]')).toBe(true);
    });

    test('deve conter um campo de input ou textarea do tipo texto com atributo name como "assunto"', () => {
      const assuntoInput = $('[name="assunto"]');
      expect(assuntoInput.length).toBeGreaterThan(0);
      expect(assuntoInput.is('input[type="text"]') || assuntoInput.is('textarea')).toBe(true);
    });

    test('deve conter um campo de input ou textarea do tipo texto com atributo name como "mensagem"', () => {
      const mensagemInput = $('[name="mensagem"]');
      expect(mensagemInput.length).toBeGreaterThan(0);
      expect(mensagemInput.is('textarea') || mensagemInput.is('input[type="text"]')).toBe(true);
    });

    test('form deve conter botão do tipo submit', () => {
      const submitButton = $('button[type="submit"], input[type="submit"]');
      expect(submitButton.length).toBeGreaterThan(0);
    });

    test('deve conter umad âncora para a rota raíz /', () => {
      const rootLink = $('a[href="/"]');
      expect(rootLink.length).toBeGreaterThan(0);
    });
  });

  describe('Route: /contato (POST) - ', () => {
    const baseContactSubmission = {
      nome: "Sophie Nguyen",
      email: "tramanh@gmail.com",
      assunto: "Sugestão de Evento",
      mensagem: "Gostaria de sugerir que vocês organizassem um evento de degustação de novos lanches!"
    };

    let finalResponse;
    let initialStatus;
    let initialLocation;
    let $;

    beforeAll(async () => {
      try {
        const responseFromPost = await axiosNoRedirect.post(`${BASE_URL}/contato`, baseContactSubmission, {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          }
        });

        initialStatus = responseFromPost.status;
        initialLocation = responseFromPost.headers.location;

        //Analyzes PRG case
        if (initialStatus >= 300 && initialStatus < 400) {
          const redirectURL = new URL(initialLocation, BASE_URL);
          expect(redirectURL.pathname).toBe('/contato-recebido');
          expect(redirectURL.search).not.toBe('');
          finalResponse = await axios.get(`${BASE_URL}${initialLocation}`);
        } else {
          finalResponse = responseFromPost;
        }
        $ = cheerio.load(finalResponse.data);

      } catch (error) {
        //Normal connectivity issue
        if (error.code === 'ECONNREFUSED') {
          throw new Error(`Connection refused at ${BASE_URL}/contato. Is the Express server running?`);
        }
        if (error.response && error.response.status >= 300 && error.response.status < 400) {
          initialStatus = error.response.status;
          initialLocation = error.response.headers.location;
          const redirectUrl = new URL(initialLocation, BASE_URL);
          expect(redirectUrl.pathname).toBe('/contato-recebido');
          expect(redirectUrl.search).not.toBe('');
          try {
            finalResponse = await axios.get(`${BASE_URL}${initialLocation}`);
            $ = cheerio.load(finalResponse.data);
          } catch (redirectError) {
            throw new Error(`Failed to follow redirect to ${initialLocation}: ${redirectError.message}`);
          }
        } else {
          finalResponse = error.response;
          if (!finalResponse) {
            throw new Error(`An unexpected error occurred while testing POST /contato: ${error.message}`);
          }
          if (finalResponse.headers['content-type'] && finalResponse.headers['content-type'].includes('html')) {
            $ = cheerio.load(finalResponse.data);
          } else {
            $ = cheerio.load('');
          }
        }
      }
    });

    test('resposta final deve possuir status code 200 com Content-type text/html', () => {
      expect(finalResponse.status).toBe(200);
      expect(finalResponse.headers['content-type']).toMatch(/html/);
    });

    test('dever retornar uma página HTML diretamente (status code 200) ou redirect para /contato-recebido (status code 3xx)', () => {
      if (initialStatus >= 300 && initialStatus < 400) {
        expect(initialStatus).toBeGreaterThanOrEqual(300);
        expect(initialStatus).toBeLessThan(400);
        const redirectUrl = new URL(initialLocation, BASE_URL);
        expect(redirectUrl.pathname).toBe('/contato-recebido');
      } else {
        expect(initialStatus).toBe(200);
        expect(initialLocation).toBeUndefined();
      }
    });

    describe('HTML Content Analysis (Final Page)', () => {
      test('página de resposta deve exibir o "nome" enviado no formulário', () => {
        expect($.html()).toContain(baseContactSubmission.nome);
      });

      test('página de resposta deve exibir o "email" enviado no formulário', () => {
        expect($.html()).toContain(baseContactSubmission.email);
      });

      test('página de resposta deve exibir o "assunto" enviado no formulário', () => {
        expect($.html()).toContain(baseContactSubmission.assunto);
      });

      test('página de resposta deve exibir o "mensagem" enviada no formulário', () => {
        expect($.html()).toContain(baseContactSubmission.mensagem);
      });

      test('deve conter umad âncora para a rota raíz /', () => {
        const rootLink = $('a[href="/"]');
        expect(rootLink.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Route: /api/lanches - ', () => {
    let response;
    let lanches;

    beforeAll(async () => {
      try {
        response = await axios.get(`${BASE_URL}/api/lanches`);
        lanches = response.data;
      } catch (error) {
        if (error.code === 'ECONNREFUSED') throw new Error(`Connection refused at ${BASE_URL}/api/lanches. Is the Express server running?`);
        throw Error(`An unexpected error occurred while testing GET /api/lanches: ${error.message}`);
      }
    });

    // --- Basic Connectivity Checks ---
    describe('Basic Connectivity and Headers', () => {
      test('deve retornar status code 200', () => {
        expect(response.status).toBe(200);
      });

      test('deve retornar header Content-type application/json', () => {
        expect(response.headers['content-type']).toMatch(/application\/json/);
      });
    });


    // --- JSON Data Structure and Type Validation ---
    describe('JSON Data Structure Validation', () => {
      test('deve retornar um array de lanches', () => {
        expect(Array.isArray(lanches)).toBe(true);
      });

      test('deve retornar um array com pelo menos 3 lanches', () => {
        expect(lanches.length).toBeGreaterThan(2);
      });

      test('cada objeto de lanche do array deve ter os seguinte atributos: id, nome ingredientes', () => {
        lanches.forEach(lanche => {
          expect(lanche).toHaveProperty('id');
          expect(lanche).toHaveProperty('nome');
          expect(lanche).toHaveProperty('ingredientes');
        });
      });

      test('cada atributo deve possuir o data type correto e não ser vazio, 0 ou null', () => {
        lanches.forEach(lanche => {
          expect(typeof lanche.id).toBe('number');
          expect(Number.isInteger(lanche.id)).toBe(true);
          expect(lanche.id).toBeGreaterThan(0);

          expect(typeof lanche.nome).toBe('string');
          expect(lanche.nome.length).toBeGreaterThan(0);

          expect(typeof lanche.ingredientes).toBe('string');
          expect(lanche.ingredientes.length).toBeGreaterThan(0);
        });
      });
    });
  }
  );
});
